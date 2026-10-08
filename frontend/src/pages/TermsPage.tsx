import { Link } from 'react-router-dom'
import { ContactEmail, LegalShell, Section } from '../components/LegalShell'

/** Página pública exigida pela Meta (URL dos Termos de Serviço do app). */
export function TermsPage() {
  return (
    <LegalShell title="Termos de Uso">
      <p>
        Estes Termos de Uso regulam o acesso e a utilização do AutoInsta, plataforma que permite a contas profissionais
        do Instagram criar automações para mensagens diretas e comentários usando as APIs oficiais da Meta. Ao criar uma
        conta ou usar a plataforma, você declara que leu e concorda com estes Termos e com a{' '}
        <Link to="/privacy">Política de Privacidade</Link>.
      </p>

      <Section title="1. Quem pode usar">
        <ul>
          <li>pessoas maiores de 18 anos ou com capacidade legal para contratar;</li>
          <li>titulares de uma conta <strong>profissional</strong> do Instagram (Empresa ou Criador de conteúdo), ou pessoas autorizadas a administrá-la;</li>
          <li>você é responsável por manter suas credenciais em sigilo e por toda atividade realizada na sua conta.</li>
        </ul>
      </Section>

      <Section title="2. O serviço">
        <p>
          O AutoInsta permite conectar uma conta do Instagram pelo login oficial do Instagram, montar fluxos de automação
          (gatilhos, condições, respostas e passos com inteligência artificial) e acompanhar suas execuções. Todas as
          ações no Instagram são feitas pelas APIs oficiais e estão sujeitas às regras e limites definidos pela Meta,
          entre eles:
        </p>
        <ul>
          <li>mensagens diretas só podem ser enviadas a quem escreveu para a conta, dentro do prazo permitido pela Meta (atualmente 24 horas);</li>
          <li>respostas privadas a comentários são limitadas a uma por comentário;</li>
          <li>recursos, permissões e limites podem ser alterados pela Meta a qualquer momento, sem aviso prévio.</li>
        </ul>
      </Section>

      <Section title="3. Uso permitido">
        <p>
          Você se compromete a usar a plataforma de forma lícita e a cumprir os Termos de Uso do Instagram, as Diretrizes
          da Comunidade e os Termos da Plataforma Meta. É proibido usar o AutoInsta para:
        </p>
        <ul>
          <li>enviar spam, mensagens enganosas, fraudulentas, abusivas, discriminatórias ou que violem direitos de terceiros;</li>
          <li>coletar dados de pessoas sem base legal ou para finalidades diferentes do atendimento a quem interagiu com a sua conta;</li>
          <li>tentar burlar limites, mecanismos de segurança ou regras da Meta, ou acessar contas e dados que não sejam seus;</li>
          <li>prejudicar o funcionamento da plataforma ou de terceiros.</li>
        </ul>
        <p>Podemos suspender ou encerrar contas que violem estes Termos, inclusive para proteger a plataforma perante a Meta.</p>
      </Section>

      <Section title="4. Conteúdo e respostas automáticas">
        <p>
          Você é o único responsável pelos fluxos que cria e pelo conteúdo enviado em seu nome, incluindo textos gerados
          por inteligência artificial. Respostas de IA podem conter erros ou imprecisões: revise as instruções dos seus
          fluxos e acompanhe os registros de execução. Você mantém os direitos sobre o seu conteúdo e nos concede apenas
          o necessário para operar as automações que configurou.
        </p>
      </Section>

      <Section title="5. Dados pessoais">
        <p>
          Ao usar a plataforma, você atua como <strong>controlador</strong> dos dados das pessoas que interagem com a sua
          conta do Instagram, e o AutoInsta atua como <strong>operador</strong>, tratando esses dados apenas para executar
          as automações configuradas. Os detalhes estão na <Link to="/privacy">Política de Privacidade</Link>.
        </p>
      </Section>

      <Section title="6. Disponibilidade e serviços de terceiros">
        <p>
          A plataforma depende de serviços de terceiros (Meta, Supabase, Render e OpenAI). Buscamos manter o serviço
          estável, mas ele é oferecido "no estado em que se encontra", sem garantia de funcionamento ininterrupto ou livre
          de erros. Mudanças, falhas ou indisponibilidades desses serviços, bem como bloqueios ou restrições aplicados pela
          Meta à sua conta, podem afetar as automações.
        </p>
      </Section>

      <Section title="7. Limitação de responsabilidade">
        <p>
          Na extensão permitida pela lei, o AutoInsta não se responsabiliza por danos indiretos, lucros cessantes, perda de
          dados, mensagens não entregues ou consequências do conteúdo enviado pelas automações configuradas por você.
          Nada nestes Termos limita direitos garantidos ao consumidor pela legislação brasileira.
        </p>
      </Section>

      <Section title="8. Cancelamento">
        <p>
          Você pode desconectar o Instagram a qualquer momento pelo painel, remover o acesso do app nas configurações do
          Instagram ou solicitar a exclusão da sua conta pelo contato abaixo. Os dados são tratados conforme a{' '}
          <Link to="/privacy">Política de Privacidade</Link>.
        </p>
      </Section>

      <Section title="9. Alterações destes Termos">
        <p>
          Podemos atualizar estes Termos. Mudanças relevantes serão comunicadas na plataforma, e a data da última
          atualização fica sempre indicada no topo desta página. O uso contínuo após a atualização significa concordância
          com a nova versão.
        </p>
      </Section>

      <Section title="10. Contato e foro">
        <p>
          Dúvidas sobre estes Termos: <ContactEmail />. Estes Termos são regidos pelas leis da República Federativa do
          Brasil, e fica eleito o foro do domicílio do consumidor para resolver eventuais controvérsias.
        </p>
      </Section>
    </LegalShell>
  )
}
