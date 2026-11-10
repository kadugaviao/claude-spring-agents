---
name: spring-boot
description: Convenções, armadilhas e mudanças de versão do Spring Boot (3.x e 4.x) para escrever, testar e revisar código Java. Usar ao criar ou alterar controllers, services, repositories, entidades JPA, migrations, configurações ou testes em projetos Spring Boot.
---

# Spring Boot

## Antes de escrever código

1. Leia a versão do Spring Boot no `pom.xml` (parent `spring-boot-starter-parent`) ou no `build.gradle` (plugin `org.springframework.boot`). Regras marcadas **[SB4]** valem só para 4.x. Em 3.x, use o equivalente indicado.
2. Use o wrapper do projeto: `./mvnw` ou `./gradlew`. Só use `mvn`/`gradle` se não houver wrapper.
3. O padrão do projeto vence estas regras. Se ele já usa Lombok, MapStruct, pacotes por camada ou outro estilo de nome, siga o projeto. As regras abaixo valem quando não há padrão.
4. O shell pode ser zsh, que aborta com `no matches found` quando um glob sem aspas não casa com nenhum arquivo. Ponha entre aspas todo padrão passado a um comando: `--include='*.java'`, `-name '*.java'`, `-Dtest='*Repository*'`.

## Estrutura

- Pacote por funcionalidade: `<base>/<feature>/` com `XController`, `XService`, `XRepository`, entidade e `dto/`.
- **Controller:** só HTTP (entrada, validação, status, mapeamento para DTO). Sem regra de negócio e sem acessar repository.
- **Service:** regra de negócio e transação. `@Transactional` no service, `@Transactional(readOnly = true)` em consultas.
- **DTOs:** `record` com Bean Validation (`@NotBlank`, `@Email`, `@Positive`...). Nunca exponha nem receba entidade JPA na API.
- **Injeção:** por construtor com campos `final`. Nunca `@Autowired` em campo.
- **Configuração:** `@ConfigurationProperties` com `record` e `@Validated`, em vez de vários `@Value`.
- **Java moderno:** records, `switch` com pattern matching, `var` quando o tipo é óbvio. Em Java 21+ com Boot 3.2+, avalie `spring.threads.virtual.enabled=true` para I/O bloqueante.

## API REST

- **Erros:** um `@RestControllerAdvice` que devolve `ProblemDetail` (RFC 9457). Exceções de domínio (ex.: `RecursoNaoEncontradoException`) viram 404/409/422 ali, não em `try/catch` no controller.
- **Validação:** `@Valid` no `@RequestBody`. A resposta 400 lista os campos inválidos.
- **Status:** `201` + header `Location` no POST, `204` no DELETE sem corpo, `404` para recurso inexistente.
- **Paginação:** receba `Pageable` e devolva um DTO de página. Não serialize `Page<Entidade>`/`PageImpl` direto. Spring Data 3.3+: `@EnableSpringDataWebSupport(pageSerializationMode = VIA_DTO)`.
- **Clientes HTTP:** `RestClient` ou interface com `@HttpExchange`. Não use `RestTemplate` em código novo: ele é deprecated no Spring Framework 7.1 (Boot 4.2), com remoção prevista no 8.0.

## Persistência (JPA)

- `spring.jpa.open-in-view=false`.
- `@ManyToOne` e `@OneToOne` são EAGER por padrão: declare `fetch = FetchType.LAZY`.
- Evite N+1 com `JOIN FETCH`, `@EntityGraph` ou projeção em DTO/record.
- Schema só via Flyway. Use `spring.jpa.hibernate.ddl-auto=validate` (nunca `update` fora de protótipo).
- Nada de `@Data` do Lombok em entidade, porque `equals`/`hashCode`/`toString` quebram com proxies e relacionamentos.
- Detalhes, convenções de migration e armadilhas de transação: [persistence.md](persistence.md)

## Segurança

- Defina um bean `SecurityFilterChain` com a DSL de lambdas. `WebSecurityConfigurerAdapter` não existe mais.
- Novo endpoint: confirme se ele precisa de autenticação/autorização e se isso está configurado.

## [SB4] O que mudou no Spring Boot 4

- **Jackson 3:** pacotes `tools.jackson.*`. As anotações continuam em `com.fasterxml.jackson.annotation`. `@JsonComponent` virou `@JacksonComponent`. Para ajustar o mapper automático, use propriedades `spring.jackson.*` ou um bean `JsonMapperBuilderCustomizer`. Um bean `JsonMapper` próprio (não `ObjectMapper`) substitui o automático por inteiro.
- **Mocks:** `@MockBean`/`@SpyBean` foram removidos. Use `@MockitoBean`/`@MockitoSpyBean`, que já existem desde o Boot 3.4 e também são preferíveis em 3.4+.
- **`@SpringBootTest`:** não configura mais MockMvc sozinho. Adicione `@AutoConfigureMockMvc`. Para chamadas HTTP em teste, use `RestTestClient` (`@AutoConfigureRestTestClient`) em vez de `TestRestTemplate`.
- **Anotações de teste mudaram de pacote:**
  - `org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest` e `...webmvc.test.autoconfigure.AutoConfigureMockMvc`
  - `org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest`
  - `org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase`
  - `org.springframework.boot.persistence.autoconfigure.EntityScan`
- **Starters de teste por tecnologia:** `spring-boot-starter-webmvc-test`, `spring-boot-starter-data-jpa-test` etc. Eles já trazem `spring-boot-starter-test`.
- **Flyway/Liquibase:** exigem `spring-boot-starter-flyway`/`spring-boot-starter-liquibase`. Só a dependência do Flyway não ativa mais a autoconfiguração.
- **Null-safety:** anotações JSpecify (`org.jspecify.annotations.Nullable`).
- **Testcontainers 2:** artefato `testcontainers-postgresql`, classe `org.testcontainers.postgresql.PostgreSQLContainer`, sem genérico. No 1.x a classe é `org.testcontainers.containers.PostgreSQLContainer<?>`.
- **Undertow:** removido. Use Tomcat ou Jetty.
- **Migração 3 → 4:** `spring-boot-properties-migrator` aponta propriedades renomeadas. Remova a dependência depois.

## Testes

- **Service:** teste unitário com JUnit 5 + Mockito + AssertJ, sem subir Spring.
- **Controller:** `@WebMvcTest(XController.class)` + `@MockitoBean` no service.
- **Repository:** `@DataJpaTest` + Testcontainers com o mesmo banco da produção. Nunca H2 se produção é Postgres.
- **Fluxo completo:** poucos `@SpringBootTest`.
- Modelos de cada tipo, nomes e o que não testar: [testing.md](testing.md)

## Antes de declarar pronto

- [ ] Compila e os testes passam: `./mvnw -q verify` (ou `./gradlew build`). Mostre o resultado do comando.
- [ ] Comportamento novo tem teste, incluindo caminho de erro.
- [ ] Mudança de schema tem migration e a entidade bate com ela.
- [ ] Nenhum segredo, `System.out` ou código comentado ficou para trás.
