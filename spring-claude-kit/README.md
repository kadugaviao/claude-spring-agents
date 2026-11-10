# Kit Claude Code para Spring Boot

Uma skill com o conhecimento de Spring Boot e quatro subagentes, um por papel. Cada subagente tem um modelo escolhido para a tarefa e travas de segurança feitas com hooks.

```
claude/                          → copiado para ~/.claude/
├── skills/spring-boot/
│   ├── SKILL.md                 convenções, armadilhas, mudanças do Boot 4 (corpo carrega quando usado)
│   ├── testing.md               modelos de teste (lido só quando precisa)
│   └── persistence.md           JPA, transações, Flyway (lido só quando precisa)
├── agents/
│   ├── spring-test-writer.md    escreve e roda testes          · sonnet · só edita src/test
│   ├── spring-reviewer.md       revisa o diff                  · opus   · só leitura
│   ├── spring-migration.md      migrations Flyway + entidades  · sonnet · não edita migration commitada
│   └── build-runner.md          roda build/testes e resume     · haiku  · só comandos mvn/gradle
└── hooks/
    ├── guard-paths.py           bloqueia edição fora do permitido
    └── bash-allowlist.py        bloqueia comandos fora da lista
templates/CLAUDE.md              modelo de CLAUDE.md para cada projeto
install.sh                       instala tudo em ~/.claude
```

## Por que esse desenho

| Decisão | Motivo |
|---|---|
| O conhecimento fica numa **skill**, não em cada agente | Só a descrição fica sempre no contexto. Na sessão principal, o Claude carrega o corpo quando a tarefa bate com a descrição. Os agentes recebem a skill pré-carregada (campo `skills`). Uma fonte só, sem duplicar. A skill não usa `paths`: com ele, ela só passa a existir na sessão depois que algum arquivo casa com os padrões, e o `skills:` dos agentes falha em silêncio antes disso (testado no Claude Code 2.1.321). |
| `SKILL.md` curto, com detalhes em `testing.md` e `persistence.md` | A Anthropic recomenda menos de 500 linhas e referências a um nível de profundidade. Cada linha custa tokens em toda chamada. |
| Só o que o Claude **não** sabe | Nada de "você é um engenheiro sênior com 10 anos". O conteúdo é o que muda o resultado: mudanças do Boot 4, armadilhas de `@Transactional` e as suas convenções. |
| Agentes **por papel**, não por tecnologia | O que diferencia um subagente são as ferramentas e permissões. Revisor só lê, tester só mexe em teste. |
| **Poucos** agentes (4) | Muitos agentes pioram a delegação automática e gastam mais. A comunidade e a Anthropic recomendam "um punhado". |
| Proibições por **hook**, não só por texto | "Não edite código de produção" no prompt é um pedido. O hook que devolve exit 2 é uma trava. |
| `description` diz **quando** usar | É a regra de roteamento que o Claude lê para decidir delegar. "Use proactively" só no `spring-reviewer` (antes de commit/PR) e no `build-runner` (build e testes). O `spring-test-writer` entra quando pedirem testes ou ao terminar uma funcionalidade, e o `spring-migration` quando a tarefa mudar o schema. Assim nenhum dispara a cada edição. |
| Formato de resposta fixo | A conversa principal recebe só o resumo, sempre no mesmo formato e fácil de agir em cima. |
| Revisor reporta só bug, não estilo | Recomendação da Anthropic para evitar revisões que levam a over-engineering. |

## Modelos

| Onde | Modelo | Por quê |
|---|---|---|
| Sessão principal | `opus` (padrão no Pro/Max) ou `opusplan` | Opus planeja e implementa melhor. `opusplan` usa Opus no plan mode e Sonnet para executar, o que economiza cota. |
| `spring-reviewer` | `opus`, effort `high` | Achar bug sutil (transação, segurança) exige raciocínio. Roda uma vez por diff e só lê. |
| `spring-test-writer` | `sonnet`, effort `medium` | Tarefa bem definida e com muitas iterações (escrever, rodar, corrigir). Sonnet é o modelo indicado para o dia a dia de código e custa menos. |
| `spring-migration` | `sonnet`, effort `high` | Tarefa curta, mas frágil. O effort mais alto faz ele pensar nos riscos (lock, perda de dados). |
| `build-runner` | `haiku`, effort `low` | Só roda comando e resume a saída. A Anthropic indica Haiku para subagentes simples. |

Um subagente sem `model` herda o modelo da sessão principal. Por isso todos aqui têm modelo fixo. Se a sua cota apertar, troque `opus` por `sonnet` no revisor. Isso é uma linha no frontmatter.

## Passo a passo

### 1. Instalar o Claude Code

```bash
curl -fsSL https://claude.ai/install.sh | bash
claude --version        # deve mostrar a versão
```

Na primeira vez que rodar `claude`, ele abre o navegador para login. Funciona com Pro, Max ou conta do Console (API).

### 2. Instalar o kit

```bash
cd spring-claude-kit
bash install.sh
```

O script copia `claude/` para `~/.claude/` e faz backup (`<arquivo>.<AAAAMMDD-HHMMSS>.bak`, sem apagar backups anteriores) de qualquer arquivo seu com o mesmo nome e conteúdo diferente. Ele precisa de `python3`, que é usado pelos hooks.

### 3. Preparar cada projeto

```bash
cd ~/projetos/telao
claude
```

Dentro do Claude Code, rode `/init` para ele gerar um `CLAUDE.md` a partir do código. Depois compare com `templates/CLAUDE.md` e mantenha o arquivo curto (menos de 200 linhas), só com o que o Claude não descobre lendo o código: comandos, convenções diferentes do padrão e o que não fazer. A seção "Fluxo de trabalho" do modelo é o que faz a sessão principal usar os subagentes. Copie essa seção.

Se você tem plugins com revisores próprios, o modelo traz a linha "Para revisar código Java/Spring Boot, use sempre o subagente spring-reviewer.". Para valer em todos os projetos, ponha essa linha também no `~/.claude/CLAUDE.md` global. Se mesmo assim o Claude escolher outro revisor com frequência, bloqueie a skill do plugin com `permissions.deny` no `.claude/settings.json` do projeto, por exemplo `"Skill(<plugin>:<skill>)"` ([Skills, "Restrict Claude's skill access"](https://code.claude.com/docs/en/skills)).

### 4. Conferir se carregou

Pergunte ao Claude `quais subagentes customizados você tem?`. Ele deve listar os quatro. Nas versões atuais, o `/agents` só mostra um lembrete, não a lista. A skill `spring-boot` está na lista de skills desde o início da sessão (pergunte `quais skills você tem?`).

Para confirmar que os agentes recebem a skill, peça: `use o spring-reviewer e peça a ele para citar a primeira linha da skill spring-boot, sem usar ferramentas`. A resposta deve ser `# Spring Boot`.

Se um agente não aparecer, rode `claude --debug-file /tmp/claude-debug.log` e procure `does not recognize or apply` (campo ignorado) e `Registered … frontmatter hook(s)` (hooks carregados). Arquivos com YAML inválido ou sem `description` são ignorados em silêncio.

### 5. Usar

Os agentes entram sozinhos quando a tarefa bate com a descrição. Para chamar um explicitamente:

```
use o spring-test-writer para cobrir o RoomService
@"spring-reviewer (agent)" revise antes do commit
crie a tabela de sessões, usando o spring-migration para o schema
roda os testes com o build-runner
```

Um fluxo típico de feature:
1. Plan mode (`Shift+Tab`) para combinar a abordagem.
2. A sessão principal implementa.
3. `spring-migration`, se mudar o schema.
4. `spring-test-writer` cobre o código novo.
5. `spring-reviewer` revisa antes do commit.

### 6. Avaliar e ajustar

A Anthropic recomenda testar contra uma linha de base. Pegue 3 tarefas reais (um teste para escrever, uma revisão, uma migration) e rode cada uma numa sessão nova com o kit e sem ele. Onde o resultado não melhorar, ajuste a skill. Onde o agente errar algo repetidamente, acrescente uma linha específica sobre esse erro.

### 7. Personalizar

- **Suas convenções:** edite `~/.claude/skills/spring-boot/SKILL.md` (Lombok, MapStruct, nomes de pacote, idioma das mensagens).
- **Para um projeto só ou para um time:** copie um agente para `<projeto>/.claude/agents/` e versione no git. O agente do projeto vence o global com o mesmo nome. Nesse caso, troque `$HOME/.claude/hooks/` por `"$CLAUDE_PROJECT_DIR"/.claude/hooks/` e copie os hooks junto. Os hooks do frontmatter de um agente de projeto só rodam depois que você aceita o diálogo de confiança da pasta. Uma sessão `claude -p` não conta como aceite.
- **Atualizar:** rode `bash install.sh` de novo. Ele faz backup do que você tiver mudado.

## Como foi testado

Os testes rodaram no Claude Code 2.1.321, com `claude -p --agents` e a versão atual dos agentes e hooks, num projeto Spring Boot 4.0.7 (Java 21) de exemplo com bugs plantados de propósito.

- **Carregamento:** os 4 agentes carregaram. Numa sessão que não abriu nenhum `.java`, o `spring-reviewer` citou literalmente a primeira linha da skill sem usar ferramentas. Isso confirma o pré-carregamento via `skills:`.
- **`spring-reviewer`** (veredito: PEDIR MUDANÇAS) achou todos os bugs plantados:
  - JPQL injection por concatenação;
  - mass assignment com entidade no `@RequestBody`, inclusive sobrescrita de outro pedido via `id`;
  - `@Transactional` em método private chamado internamente;
  - chamada HTTP no fluxo transacional;
  - `findAll` filtrado em memória;
  - entidade exposta na API;
  - POST sem `@Valid` e sem 201;
  - regra de negócio do Javadoc não implementada;
  - falta de testes.

  Também apontou endpoints sem autenticação e entidade sem migration Flyway. Não reclamou de estilo (havia uma variável `x` de propósito). O hook bloqueou um `git status && git diff`, e o agente seguiu com um comando por vez. Os hashes de `src/main` e do `pom.xml` não mudaram.
- **`spring-test-writer`:** recebeu a ordem de "corrigir também o código de produção" e recusou. Antes do build, conferiu o wrapper com `find . -maxdepth 1 -name mvnw -o -maxdepth 1 -name gradlew`, não achou e usou `mvn`. Rodou a classe nova (`mvn -q test -Dtest=PedidoServiceTest`) e depois o módulo inteiro (`mvn -q test`), e a linha "Comando:" mostrou os dois. Escreveu 9 testes (Mockito + AssertJ). Quatro deles falham de propósito e demonstram o bug do percentual sem validação, que foi reportado com a correção sugerida. Rodando de forma independente, o resultado conferiu: `Tests run: 9, Failures: 4`. Numa rodada anterior, com o mesmo pedido, ele escreveu 10 testes, 5 deles falhando, porque também cobriu o percentual nulo. O número varia entre rodadas, mas o bug é o mesmo. Os hashes de `src/main` e do `pom.xml` não mudaram.
- **Busca sem Glob/Grep:** pedido para achar todos os usos de `@Transactional`, o `spring-reviewer` buscou com `grep -rn` pelo Bash, o hook liberou, e ele achou o único uso (`PedidoService.java:26`), separado do import.
- **`build-runner`** (Haiku): rodou `mvn -q -B verify` no projeto com os 9 testes acima e informou "4 falhas de 9 testes", que confere com a contagem independente. O log de debug mostrou "Registered 1 frontmatter hook(s) from agent 'build-runner'" e nenhum `does not recognize or apply`. As tentativas com `;` (`…; echo "EXIT=${PIPESTATUS[0]}"`) foram bloqueadas, e ele seguiu com um comando por vez.
- **Lista de caracteres permitidos, num teste real:** o `spring-reviewer` buscou `@Transactional` e as chamadas HTTP com `grep -rn --include='*.java' …` e `find … -not -path '*/.git/*'`, e o hook liberou. Ele achou o `@Transactional` ineficaz (private, com chamada interna) e o `RestClient` dentro do fluxo. A primeira tentativa, que juntava os comandos com `;`, foi bloqueada.
- **Hooks:** 252 casos, todos passando, testados isoladamente via `sh -c` e `bash -c` com o comando literal do frontmatter (path traversal, symlink, caminho fora do projeto, `;`, `&&`, `$(`, redirecionamento, aspas, pipe para `xargs`/`sort -o`, `git push`, `git branch -D`, migration commitada vs. só staged vs. nova, migration fora de `db/migration`, variáveis antes do comando, `git --no-pager` e `git -C` com aspas, `find`/`grep` como busca, `find -exec`/`-delete`/`-rm`/`-fprint*`/`-fls`, `grep | xargs`, `find -name "-exec"` liberado, `exec:`/`antrun:`/`-Dexec.*` no Maven, `-I`/`--init-script`/`-Dorg.gradle.jvmargs` no Gradle, expansões do shell (`{-delete,-print}`, `$'…'`, `${X:-…}`, `$"…"`, qualificador `*(e:…)` do zsh), `find \( … \)` liberado, `grep 'foo$'` liberado e o `spring-migration` restrito ao projeto). Comandos que passavam pelo hook antigo e apagavam arquivos foram reexecutados de verdade numa pasta descartável e agora são bloqueados.

## Limites das travas

Os hooks são guarda-corpos, não um sandbox:
- Nos agentes com Bash, cada chamada é um comando só. Fora de aspas, o hook só aceita letras, números, espaço e `_ . / : = , @ % + - * ? ~ |`, mais `\(`/`\)` no `find` e o `2>&1`. Assim ficam bloqueados encadeamento (`;`, `&&`, `cd … &&`), redirecionamento (`>`, `2>/dev/null`), `$…` em qualquer forma (`$(…)`, `${…}`, `$'…'`, `$"…"`), chaves `{a,b}`, `[`, `!`, `#` e crase. Expansões assim enganavam a checagem por palavra: `find . {-delete,-print}` passava e apagava arquivos. Dentro de aspas simples vale tudo (ex.: `grep -rn 'foo$' src`). Dentro de aspas duplas, `$` e crase bloqueiam. Antes do comando, só as variáveis `MAVEN_OPTS`, `GRADLE_OPTS` e `JAVA_HOME`. Pipes só para `grep`/`find`/`head`/`tail`/`wc`/`cut`, nunca `xargs`. Se o agente reclamar de bloqueio, é isso.
- **Glob e Grep não existem no Linux, macOS e WSL.** O Claude Code tira essas duas ferramentas de quem tem Bash e busca com `find` e `grep` pelo Bash (versões embutidas de `bfs` e `ugrep`). Essas buscas chegam aos hooks como chamadas Bash ([Tools reference, "Glob tool behavior"](https://code.claude.com/docs/en/tools-reference#glob-tool-behavior)). Por isso o `bash-allowlist.py` libera `find` e `grep` nos 4 agentes, como primeiro comando ou depois de um pipe. No `find`, bloqueia `-exec`, `-execdir`, `-ok`, `-okdir`, `-delete`, `-rm` (sinônimo de `-delete` no bfs), `-fprint`, `-fprint0`, `-fprintf` e `-fls`. O valor de opções como `-name`, `-path`, `-regex` e `-type` não conta como ação, então `find . -name "-exec"` passa. Os agentes mantêm `Grep, Glob` em `tools:`: no Linux não atrapalham e no Windows voltam a funcionar.
- O Bash do `spring-test-writer` e do `spring-migration` só aceita Maven/Gradle, `find`/`grep` e git de leitura. No Maven, o hook bloqueia `exec:…`, `antrun:…`, `-Dexec.*` e as coordenadas completas dos dois plugins. No Gradle, bloqueia `-I`, `--init-script` e `-Dorg.gradle.jvmargs`. **Essa trava só protege de verdade o `build-runner`**, que não escreve arquivos. O `spring-test-writer` e o `spring-migration` executam código ao rodar os testes (e, no migration, o código) que eles mesmos escrevem. Para eles, a trava de Maven/Gradle é só um guarda-corpo. Ela também não cobre tudo: `--define`, `-f outro/pom.xml`, `MAVEN_OPTS`/`GRADLE_OPTS` e as opções `-c`/`-p`/`-g` do Gradle continuam liberados.

  Os plugins já declarados no `pom.xml`/`build.gradle` rodam normalmente no build, inclusive `exec`/`antrun` amarrados a uma fase. `flyway:clean` continua proibido só no prompt. Para isolar de verdade, o sandbox do Claude Code (`/sandbox`, no macOS, Linux e WSL2) restringe arquivos e rede do Bash. Mas ele é incompatível com `docker` ([Sandboxing](https://code.claude.com/docs/en/sandboxing)), então só serve para projetos que não usam Testcontainers.
- O `spring-migration` só edita arquivos dentro do projeto (`$CLAUDE_PROJECT_DIR`, ou o cwd). O guard reconhece `V<n>__*.sql`/`.java` em qualquer pasta do projeto. Fora de um repositório git ele não sabe o que foi commitado e libera.

Para travas globais, adicione em `~/.claude/settings.json`:

```json
{ "permissions": { "deny": ["Bash(git push *)", "Bash(rm -rf *)"] } }
```

## Fontes

- [Subagentes – Claude Code Docs](https://code.claude.com/docs/en/sub-agents)
- [Skills – Claude Code Docs](https://code.claude.com/docs/en/skills)
- [Boas práticas para escrever skills – Claude Platform Docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Best practices for Claude Code – Anthropic](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Quando usar CLAUDE.md, skills, hooks e subagentes – Anthropic](https://claude.com/resources/articles/steering-claude-code-skills-hooks-rules-subagents-and-more)
- [Configuração de modelos – Claude Code Docs](https://code.claude.com/docs/en/model-config)
- [Gerenciar custos – Claude Code Docs](https://code.claude.com/docs/en/costs)
- [Hooks – Claude Code Docs](https://code.claude.com/docs/en/hooks)
- [Spring Boot 4.0 Migration Guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide)
- [Claude Code Template for Spring Boot – Piotr Minkowski](https://piotrminkowski.com/?p=16088)
