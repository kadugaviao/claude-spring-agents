# <Nome do projeto>

<Uma ou duas frases: o que o sistema faz e para quem.>

## Stack
- Java <21|25>, Spring Boot <4.1|4.0>, <Maven|Gradle>
- <PostgreSQL 17> com Flyway · <Spring Security + JWT> · <outros: Redis, RabbitMQ, WebRTC...>

## Comandos
- Build e testes: `./mvnw -q verify`
- Um teste: `./mvnw -q test -Dtest=NomeDaClasseTest`
- Rodar local: `docker compose up -d && ./mvnw spring-boot:run -Dspring-boot.run.profiles=dev`
- <Qualquer comando fora do padrão, ex.: gerar código, seed do banco>

## Estrutura
- `src/main/java/<pacote>/<feature>/`: um pacote por funcionalidade (controller, service, repository, dto)
- <Pastas ou módulos que não são óbvios e o que cada um faz>

## Convenções que diferem do padrão
<!-- Só o que o Claude não descobriria lendo o código. Apague o que não se aplica. -->
- <ex.: Usamos Lombok só para @Getter/@Builder em DTOs, nunca em entidades>
- <ex.: Mensagens de erro e nomes de domínio em português>
- <ex.: Commits no formato Conventional Commits, em português>

## Fluxo de trabalho
- Tarefa com 3+ passos ou decisão de arquitetura: planeje antes (plan mode) e espere aprovação.
- Para rodar a suíte completa, use o subagente build-runner.
- Depois de implementar, use o spring-test-writer para cobrir o código novo.
- Mudança de schema passa pelo spring-migration.
- Para revisar código Java/Spring Boot, use sempre o subagente spring-reviewer.
- Antes de commitar, rode o spring-reviewer e resolva os problemas CRÍTICO/ALTO.
- Só diga que terminou depois de mostrar os testes passando.

## Não fazer
- <ex.: Não editar migrations já commitadas em src/main/resources/db/migration>
- <ex.: Não alterar application-prod.yml>
- <ex.: Não adicionar dependências sem perguntar>
