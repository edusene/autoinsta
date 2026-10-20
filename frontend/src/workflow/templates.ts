import type { Graph } from '../types'

// Modelos prontos exibidos em "Novo workflow". Todos passam na validação do backend.
export interface WorkflowTemplate {
  id: string
  name: string
  description: string
  graph: Graph | null // null = em branco (o backend cria só o gatilho)
}

const node = (id: string, type: string, x: number, y: number, config: Record<string, unknown> = {}) => ({
  id,
  type,
  position: { x, y },
  data: { config },
})

const edge = (source: string, target: string, sourceHandle: string | null = null) => ({
  id: `e-${source}-${sourceHandle ?? 'default'}-${target}`,
  source,
  target,
  sourceHandle,
})

const AI_INSTRUCTIONS = 'Você é o atendente da nossa loja no Instagram. Seja simpático e objetivo.'

// Modo estrito: a IA só usa estes fatos; sem certeza, o sistema envia a resposta fixa
const AI_STRICT = {
  mode: 'strict',
  knowledge: [
    'Horário de atendimento: segunda a sexta, das 9h às 18h.',
    'Catálogo e preços: https://seusite.com',
    'Entrega: para todo o Brasil.',
  ].join('\n'),
  fallback_text: 'Boa pergunta! Vou chamar alguém da equipe para te responder certinho. 😊',
}

export const WORKFLOW_TEMPLATES: WorkflowTemplate[] = [
  {
    id: 'blank',
    name: 'Em branco',
    description: 'Começa só com o gatilho de mensagem recebida.',
    graph: null,
  },
  {
    id: 'ai-dm',
    name: 'Atendimento com IA nas DMs',
    description: 'Toda DM recebida é respondida pela IA.',
    graph: {
      nodes: [
        node('gatilho', 'trigger.message_received', 80, 40),
        node('ia', 'action.ai', 80, 200, {
          ...AI_STRICT,
          instructions: AI_INSTRUCTIONS,
          input: '{{message.text}}',
          max_output_tokens: 400,
          save_as: 'resposta_ia',
        }),
        node('responder', 'action.send_message', 80, 380, { text: '{{ai.response}}' }),
      ],
      edges: [edge('gatilho', 'ia'), edge('ia', 'responder')],
    },
  },
  {
    id: 'keyword-dm',
    name: 'Palavra-chave + IA',
    description: 'Perguntas sobre preço recebem resposta fixa; o resto é respondido pela IA.',
    graph: {
      nodes: [
        node('gatilho', 'trigger.message_received', 260, 20),
        node('preco', 'condition.check', 260, 170, {
          left: '{{message.text}}',
          operator: 'contains_any',
          value: 'preço, preco, valor, quanto custa',
          case_sensitive: false,
        }),
        node('resp_preco', 'action.send_message', 40, 360, {
          text: 'Oi, {{contact.username}}! Nossa tabela de preços está no link da bio. Quer que eu te ajude a escolher?',
        }),
        node('ia', 'action.ai', 480, 360, {
          ...AI_STRICT,
          instructions: AI_INSTRUCTIONS,
          input: '{{message.text}}',
          max_output_tokens: 400,
          save_as: 'resposta_ia',
        }),
        node('resp_ia', 'action.send_message', 480, 540, { text: '{{ai.response}}' }),
      ],
      edges: [
        edge('gatilho', 'preco'),
        edge('preco', 'resp_preco', 'true'),
        edge('preco', 'ia', 'false'),
        edge('ia', 'resp_ia'),
      ],
    },
  },
  {
    id: 'follow-gate',
    name: 'Seguir para receber o link',
    description: 'Quem manda "EU QUERO" por DM recebe o link se já segue a conta; se não, é convidado a seguir.',
    graph: {
      nodes: [
        node('gatilho', 'trigger.message_received', 260, 20),
        node('palavra', 'condition.check', 260, 170, {
          left: '{{message.text}}',
          operator: 'contains_any',
          value: 'eu quero, quero, link',
          case_sensitive: false,
        }),
        node('segue', 'condition.follows', 260, 340, { on_unknown: 'false' }),
        node('link', 'action.send_message', 40, 520, {
          text: 'Obrigado por seguir, {{contact.username}}! 💜 Aqui está o link: https://seusite.com',
          track_links: true,
        }),
        node('pedir', 'action.send_message', 480, 520, {
          text: 'Quase lá! Me segue aqui no Instagram e manda "EU QUERO" de novo que eu te envio o link 😉',
        }),
      ],
      edges: [
        edge('gatilho', 'palavra'),
        edge('palavra', 'segue', 'true'),
        edge('segue', 'link', 'true'),
        edge('segue', 'pedir', 'false'),
      ],
    },
  },
  {
    id: 'buttons-menu',
    name: 'Menu com botões',
    description: 'Responde a DM com botões; cada escolha segue um caminho e quem pede atendimento recebe a tag "humano".',
    graph: {
      nodes: [
        node('gatilho', 'trigger.message_received', 260, 20),
        node('menu', 'action.send_buttons', 260, 170, {
          text: 'Oi, {{contact.username}}! Como posso te ajudar? 👇',
          style: 'buttons',
          buttons: [
            { id: 'precos', title: 'Ver preços', type: 'reply' },
            { id: 'humano', title: 'Falar com humano', type: 'reply' },
            { id: 'site', title: 'Abrir o site', type: 'url', url: 'https://seusite.com' },
          ],
          timeout_minutes: 60,
          track_links: true,
        }),
        node('precos_msg', 'action.send_message', 620, 150, {
          text: 'Nossa tabela completa está aqui: https://seusite.com/precos',
          track_links: true,
        }),
        node('tag_humano', 'action.add_tag', 620, 330, { tag: 'humano' }),
        node('humano_msg', 'action.send_message', 620, 480, {
          text: 'Combinado! Alguém da equipe vai te responder por aqui em breve. 🙌',
        }),
      ],
      edges: [
        edge('gatilho', 'menu'),
        edge('menu', 'precos_msg', 'precos'),
        edge('menu', 'tag_humano', 'humano'),
        edge('tag_humano', 'humano_msg'),
      ],
    },
  },
  {
    id: 'follow-up',
    name: 'Follow-up se não responder',
    description: 'Faz uma pergunta e espera a resposta; se a pessoa não responder em 2h, envia um lembrete.',
    graph: {
      nodes: [
        node('gatilho', 'trigger.message_received', 260, 20),
        node('pergunta', 'action.send_message', 260, 170, {
          text: 'Oi, {{contact.username}}! Qual produto te interessou? Me conta que eu te ajudo 😊',
        }),
        node('espera', 'action.wait_reply', 260, 330, { timeout_minutes: 120 }),
        node('obrigado', 'action.send_message', 40, 500, {
          text: 'Perfeito, anotei: "{{reply.text}}". Já te mando os detalhes!',
        }),
        node('lembrete', 'action.send_message', 480, 500, {
          text: 'Oi de novo! Ainda posso te ajudar com alguma coisa? Nosso catálogo: https://seusite.com',
          track_links: true,
        }),
      ],
      edges: [
        edge('gatilho', 'pergunta'),
        edge('pergunta', 'espera'),
        edge('espera', 'obrigado', 'replied'),
        edge('espera', 'lembrete', 'timeout'),
      ],
    },
  },
  {
    id: 'welcome',
    name: 'Boas-vindas a novos contatos',
    description: 'Na 1ª mensagem de alguém, envia uma saudação com o link principal.',
    graph: {
      nodes: [
        node('gatilho', 'trigger.new_contact', 80, 40),
        node('boas_vindas', 'action.send_message', 80, 200, {
          text: 'Oi, {{contact.username}}! Que bom ter você por aqui 💜 Confira nossos produtos: https://seusite.com',
          track_links: true,
        }),
      ],
      edges: [edge('gatilho', 'boas_vindas')],
    },
  },
  {
    id: 'story-mention',
    name: 'Agradecer menção no story',
    description: 'Quem marca a conta em um story recebe um agradecimento com cupom.',
    graph: {
      nodes: [
        node('gatilho', 'trigger.story_mention', 80, 40),
        node('obrigado', 'action.send_message', 80, 200, {
          text: 'Obrigado pela menção, {{contact.username}}! 🙌 Use o cupom OBRIGADO10 na próxima compra.',
        }),
      ],
      edges: [edge('gatilho', 'obrigado')],
    },
  },
  {
    id: 'comment-dm',
    name: 'Comentou "EU QUERO" → DM',
    description: 'Quem comenta a palavra-chave recebe o link por DM e uma resposta pública.',
    graph: {
      nodes: [
        node('gatilho', 'trigger.comment_received', 80, 20),
        node('palavra', 'condition.check', 80, 170, {
          left: '{{comment.text}}',
          operator: 'contains_any',
          value: 'eu quero, quero, link',
          case_sensitive: false,
        }),
        node('dm', 'action.private_reply', 80, 360, {
          text: 'Oi, {{contact.username}}! Aqui está o link que você pediu: https://seusite.com 😉',
          track_links: true,
        }),
        node('publico', 'action.reply_comment', 80, 520, { text: 'Te enviei no direct! 📩' }),
      ],
      edges: [edge('gatilho', 'palavra'), edge('palavra', 'dm', 'true'), edge('dm', 'publico')],
    },
  },
]
