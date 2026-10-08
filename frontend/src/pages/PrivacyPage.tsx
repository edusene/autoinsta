import { ContactEmail, LegalShell, Section } from '../components/LegalShell'

/** Página pública exigida pela Meta (URL da Política de Privacidade do app). */
export function PrivacyPage() {
  const contact = <ContactEmail />

  return (
    <LegalShell title="Política de Privacidade">
          <p>
            O AutoInsta é uma plataforma que permite a contas profissionais do Instagram automatizar respostas a
            mensagens diretas e comentários, usando exclusivamente as APIs oficiais da Meta. Esta política explica quais
            dados tratamos, para quê, com quem os compartilhamos e como você pode exercer seus direitos, em conformidade
            com a Lei Geral de Proteção de Dados (Lei nº 13.709/2018 — LGPD) e com os Termos da Plataforma Meta.
          </p>

          <Section title="1. Dados que tratamos">
            <p><strong>a) Usuários da plataforma</strong> (quem cria conta no AutoInsta):</p>
            <ul>
              <li>e-mail e senha de acesso (a senha é armazenada de forma criptografada pelo provedor de autenticação; nunca temos acesso a ela em texto puro);</li>
              <li>workflows, configurações e registros (logs) das automações criadas.</li>
            </ul>
            <p><strong>b) Conta do Instagram conectada</strong> (autorizada pelo próprio usuário via login oficial do Instagram):</p>
            <ul>
              <li>ID da conta profissional, nome de usuário, nome, tipo de conta e foto de perfil;</li>
              <li>token de acesso concedido pela Meta, armazenado <strong>criptografado</strong> e nunca exibido no navegador;</li>
              <li>permissões concedidas: <code>instagram_business_basic</code>, <code>instagram_business_manage_messages</code> e <code>instagram_business_manage_comments</code>.</li>
            </ul>
            <p><strong>c) Pessoas que interagem com a conta conectada</strong> (enviam mensagens ou comentam):</p>
            <ul>
              <li>identificador do Instagram atribuído pela Meta (IGSID), nome de usuário e nome, quando disponibilizados pela Meta;</li>
              <li>conteúdo das mensagens diretas e comentários recebidos, ID da publicação comentada e data/hora da interação.</li>
            </ul>
            <p>Não coletamos dados de pessoas que não interagiram com a conta conectada, não fazemos scraping e não acessamos dados além do que a Meta envia pelas APIs oficiais.</p>
          </Section>

          <Section title="2. Para que usamos os dados">
            <ul>
              <li>executar as automações configuradas pelo usuário (por exemplo, responder uma mensagem ou um comentário);</li>
              <li>exibir ao usuário o histórico de contatos, execuções e erros, para acompanhamento e suporte;</li>
              <li>manter a conexão com o Instagram ativa (renovação do token) e diagnosticar falhas;</li>
              <li>garantir a segurança da plataforma e cumprir obrigações legais.</li>
            </ul>
            <p>
              Bases legais (LGPD, art. 7º): execução de contrato com o usuário da plataforma, legítimo interesse para
              operar as automações solicitadas por ele e cumprimento de obrigação legal. <strong>Não vendemos dados</strong> e
              não os usamos para publicidade.
            </p>
          </Section>

          <Section title="3. Uso de inteligência artificial">
            <p>
              Quando o usuário inclui um passo de IA em uma automação, enviamos à OpenAI <strong>somente</strong> as
              instruções e o texto configurados nesse passo (normalmente o texto da mensagem recebida), para gerar a
              resposta. Não enviamos tokens, senhas nem identificadores internos. As requisições são feitas pela API da
              OpenAI com a opção de não armazenamento de respostas ativada.
            </p>
          </Section>

          <Section title="4. Com quem compartilhamos">
            <p>Apenas com fornecedores necessários para operar o serviço, que atuam como operadores de dados:</p>
            <ul>
              <li><strong>Meta Platforms</strong> — envio e recebimento de mensagens e comentários pelas APIs oficiais do Instagram;</li>
              <li><strong>Supabase</strong> — banco de dados e autenticação;</li>
              <li><strong>Render</strong> — hospedagem da aplicação;</li>
              <li><strong>OpenAI</strong> — somente quando há passo de IA configurado (ver item 3).</li>
            </ul>
            <p>Esses fornecedores podem processar dados fora do Brasil, com as salvaguardas previstas na LGPD. Também podemos compartilhar dados quando exigido por lei ou ordem judicial.</p>
          </Section>

          <Section title="5. Armazenamento e segurança">
            <ul>
              <li>tráfego protegido por HTTPS; tokens do Instagram criptografados em repouso;</li>
              <li>cada usuário acessa apenas os próprios dados; o banco não é acessível diretamente pelo navegador;</li>
              <li>registros técnicos não armazenam tokens, chaves ou senhas.</li>
            </ul>
          </Section>

          <Section title="6. Retenção e exclusão">
            <ul>
              <li><strong>Desconectar o Instagram</strong> (página Instagram do painel) apaga imediatamente o token de acesso.</li>
              <li><strong>Remover o app nas configurações do Instagram</strong> (Configurações → Apps e sites) faz a Meta nos notificar; desconectamos a conta automaticamente.</li>
              <li><strong>Solicitar exclusão de dados</strong> pela Meta remove a conta conectada, seus tokens, contatos e históricos associados, e gera um código de confirmação.</li>
              <li>Também é possível pedir a exclusão completa da conta da plataforma pelo contato abaixo.</li>
            </ul>
            <p>Mantemos os dados apenas enquanto a conta estiver ativa ou pelo tempo necessário para cumprir obrigações legais.</p>
          </Section>

          <Section title="7. Seus direitos">
            <p>
              Você pode solicitar confirmação de tratamento, acesso, correção, anonimização, portabilidade, exclusão,
              informação sobre compartilhamento e revogação de consentimento (LGPD, art. 18). Pessoas que interagiram com
              uma conta conectada também podem exercer esses direitos.
            </p>
          </Section>

          <Section title="8. Contato">
            <p>Para dúvidas ou solicitações sobre privacidade, entre em contato pelo e-mail {contact}.</p>
          </Section>

          <Section title="9. Alterações">
            <p>Podemos atualizar esta política. A data da última atualização fica sempre indicada no topo desta página.</p>
          </Section>
    </LegalShell>
  )
}
