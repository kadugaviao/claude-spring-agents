# Testes em Spring Boot

Conteúdo: 1. Escolha do tipo · 2. Unitário de service · 3. Controller · 4. Repository · 5. Integração completa · 6. Regras e nomes · 7. Comandos

## 1. Escolha do tipo

| Alvo | Tipo | Sobe Spring? |
|---|---|---|
| Service, regra de negócio, mapper | Unitário (Mockito) | Não |
| Controller (status, validação, JSON) | `@WebMvcTest` | Só a camada web |
| Repository, query customizada | `@DataJpaTest` + Testcontainers | Só JPA |
| Fluxo ponta a ponta, segurança, config | `@SpringBootTest` | Tudo |

Prefira o tipo mais leve que prova o comportamento.

## 2. Unitário de service

```java
@ExtendWith(MockitoExtension.class)
class PedidoServiceTest {

    @Mock PedidoRepository repository;
    @InjectMocks PedidoService service;

    @Test
    void buscar_quandoNaoExiste_lancaRecursoNaoEncontrado() {
        when(repository.findById(42L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.buscar(42L))
            .isInstanceOf(RecursoNaoEncontradoException.class)
            .hasMessageContaining("42");
    }
}
```

## 3. Controller

```java
@WebMvcTest(PedidoController.class)
class PedidoControllerTest {

    @Autowired MockMvc mvc;
    @MockitoBean PedidoService service;   // Boot < 3.4: @MockBean

    @Test
    void criar_comCorpoInvalido_retorna400ComCampos() throws Exception {
        mvc.perform(post("/pedidos")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {"clienteId": null, "itens": []}
                    """))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.detail").exists());

        verifyNoInteractions(service);
    }
}
```

- Se o projeto tiver Spring Security, `@WebMvcTest` carrega os filtros. Use `@WithMockUser` ou importe a config de segurança e teste 401/403 também.
- Em Boot 3.4+, `MockMvcTester` (asserts no estilo AssertJ) é uma alternativa ao `MockMvc`. Siga o que o projeto já usa.

## 4. Repository

```java
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)   // redundante no Boot 4: o padrão já é NON_TEST
@Testcontainers
class PedidoRepositoryTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer postgres = new PostgreSQLContainer("postgres:17-alpine");
    // Testcontainers 1.x: PostgreSQLContainer<?> e new PostgreSQLContainer<>(...)

    @Autowired PedidoRepository repository;

    @Test
    void buscarPorCliente_retornaSoPedidosDoCliente() { /* ... */ }
}
```

- Com Flyway no classpath, as migrations rodam no container. Isso também valida o schema contra as entidades.
- Teste queries customizadas (`@Query`, métodos derivados complexos) e projeções. Não teste `save`/`findById` puros.

## 5. Integração completa

```java
@SpringBootTest
@AutoConfigureMockMvc          // obrigatório no Boot 4
@Testcontainers
class PedidoFluxoIT { /* ... */ }
```

- Para chamar a API real numa porta, use `RestTestClient` no Boot 4 e `TestRestTemplate` no 3.x.
- Para várias classes de integração, reaproveite o container: uma classe base abstrata ou `@ImportTestcontainers`.

## 6. Regras e nomes

- **Nome:** `metodo_quandoCondicao_resultadoEsperado`, ou o padrão que o projeto já usa.
- Um comportamento por teste, com a estrutura Arrange / Act / Assert visível.
- AssertJ (`assertThat`) em vez de `assertEquals`.
- **Cubra:** caminho feliz, validação, não encontrado, conflito/duplicidade, limites (lista vazia, zero, null).
- **Proibido:** `Thread.sleep` (use Awaitility), dependência da ordem dos testes, chamadas reais a serviços externos (use WireMock ou mock do client), dados aleatórios sem seed.
- **Não teste:** getters/setters, código gerado, o próprio framework.

## 7. Comandos

| Ação | Maven | Gradle |
|---|---|---|
| Uma classe | `./mvnw -q test -Dtest=PedidoServiceTest` | `./gradlew test --tests PedidoServiceTest` |
| Um método | `./mvnw -q test -Dtest='PedidoServiceTest#buscar*'` | `./gradlew test --tests 'PedidoServiceTest.buscar*'` |
| Tudo | `./mvnw -q verify` | `./gradlew build` |
| Módulo | `./mvnw -q test -pl modulo -am` | `./gradlew :modulo:test` |

Relatórios de falha: `target/surefire-reports/*.txt` (Maven) e `build/test-results/test/*.xml` (Gradle; o HTML fica em `build/reports/tests/test/`).
