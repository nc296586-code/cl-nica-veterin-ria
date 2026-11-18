CLÍNICA VETERINÁRIA — VERSÃO WEB

Esta pasta contém a adaptação web do projeto desktop. Ela abre no navegador.
A aplicação inclui login, tutores, pets e agendamentos.

TESTAR NO COMPUTADOR (Windows)
1. Instale Python 3.10 ou superior.
2. Extraia esta pasta.
3. Abra a pasta no VS Code.
4. No terminal execute:
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
5. Abra http://127.0.0.1:5000 no navegador.

LOGIN DE DEMONSTRAÇÃO
Usuário: admin
Senha: 123456

PUBLICAR NA INTERNET
O arquivo render.yaml está preparado para iniciar a configuração no Render:
1. Crie um repositório no GitHub e envie os arquivos desta pasta.
2. No Render, escolha New > Blueprint e conecte o repositório.
3. Confira o serviço e publique.
4. O Render fornecerá um endereço público HTTPS.

IMPORTANTE
- Este pacote ainda NÃO está publicado. Não existe link público até concluir a publicação.
- Para publicar, será necessário entrar nas contas de hospedagem/GitHub e confirmar as etapas.
- A versão usa SQLite local. Em hospedagem gratuita, o armazenamento pode ser temporário e os dados podem ser perdidos em reinicializações ou novas implantações. Para uso real, configure banco persistente e armazenamento seguro.
- Antes de publicar, altere as credenciais de demonstração e configure FLASK_SECRET_KEY e FERNET_KEY como variáveis secretas no serviço de hospedagem.
- Use apenas dados fictícios para a apresentação escolar. Não cadastre CPFs reais.
