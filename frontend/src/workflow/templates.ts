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

const AI_INSTRUCTIONS =
  'Você é o atendente de uma loja no Instagram. Responda em português, de forma simpática e objetiva, ' +
  'em no máximo 3 frases. Se não souber a resposta, diga que um atendente humano vai responder em breve.'

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
    id: 'welcome',
    name: 'Boas-vindas a novos contatos',
    description: 'Na 1ª mensagem de alguém, envia uma saudação com o link principal.',
    graph: {
      nodes: [
        node('gatilho', 'trigger.new_contact', 80, 40),
        node('boas_vindas', 'action.send_message', 80, 200, {
          text: 'Oi, {{contact.username}}! Que bom ter você por aqui 💜 Confira nossos produtos: https://seusite.com',
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
        }),
        node('publico', 'action.reply_comment', 80, 520, { text: 'Te enviei no direct! 📩' }),
      ],
      edges: [edge('gatilho', 'palavra'), edge('palavra', 'dm', 'true'), edge('dm', 'publico')],
    },
  },
]
