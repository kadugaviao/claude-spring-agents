# Persistência: JPA, transações e Flyway

Conteúdo: 1. Transações · 2. Entidades · 3. Consultas · 4. Migrations Flyway · 5. Mudanças arriscadas de schema

## 1. Transações

- `@Transactional` funciona via proxy, então três casos **não** abrem transação:
  - método `private`;
  - chamada interna (`this.metodo()`) dentro do mesmo bean;
  - classe não gerenciada pelo Spring.
- Exceção checked **não** faz rollback por padrão. Use `rollbackFor = Exception.class` ou exceções unchecked de domínio.
- Não faça chamadas HTTP externas ou longas dentro de uma transação, porque ela segura a conexão do pool.
- `readOnly = true` em consultas. É mais barato e evita flush acidental.
- `LazyInitializationException`: carregue o que precisa na query (fetch join, entity graph, DTO). Não use EAGER nem `open-in-view` como solução.

## 2. Entidades

- `@Id @GeneratedValue(strategy = GenerationType.IDENTITY)` (Postgres `bigint generated always as identity`), ou `SEQUENCE` se o projeto usar sequências.
- `@Column(nullable = false, length = N)` deve bater com a migration. `ddl-auto=validate` acusa a diferença.
- **Relacionamentos:**
  - `@ManyToOne(fetch = LAZY)`.
  - `@OneToMany(mappedBy = ...)` sem cascade amplo.
  - Prefira consultas a coleções grandes mapeadas.
- **`equals`/`hashCode`:** com base no id e estáveis para entidade nova (`getClass().hashCode()` no hashCode), ou não sobrescreva.
- **Enums:** `@Enumerated(EnumType.STRING)`, nunca `ORDINAL`.
- **Datas:** `Instant`/`OffsetDateTime` para momentos e `LocalDate` para datas. Coluna `timestamptz` no Postgres.
- **Dinheiro:** `BigDecimal` + `numeric(19,2)`, nunca `double`.

## 3. Consultas

- **N+1:** coleção acessada em loop após `findAll` → `JOIN FETCH` ou `@EntityGraph(attributePaths = ...)`.
- `JOIN FETCH` com paginação em coleção gera paginação em memória (aviso HHH90003004). Pagine os ids primeiro e depois busque com fetch.
- Projeção em `record` para listagens: `select new com.app.PedidoResumo(p.id, p.total) from Pedido p`.
- Toda nova consulta frequente em coluna sem índice precisa de índice na migration.
- `@Modifying` em update/delete em lote + `clearAutomatically = true` quando o contexto tiver entidades afetadas.

## 4. Migrations Flyway

- **Local padrão:** `src/main/resources/db/migration`. Confira `spring.flyway.locations`.
- **Nome:** `V<versão>__<descricao_em_snake_case>.sql`, com dois underscores. Use a versão seguinte à maior existente e siga o formato já usado (`V7`, `V1_7` ou timestamp `V20261109153000`).
- **Nunca edite uma migration já commitada.** Ela pode ter rodado em algum banco, e o checksum quebraria. Corrija com uma migration nova.
- Uma mudança lógica por arquivo.
- **Constraints e índices com nome explícito:** `pk_<tabela>`, `fk_<tabela>_<referenciada>`, `uk_<tabela>_<colunas>`, `idx_<tabela>_<colunas>`, `ck_<tabela>_<regra>`.
- Toda FK ganha índice na coluna de origem, porque o Postgres não cria sozinho.
- Migrations de dados ficam separadas das de estrutura e são idempotentes quando possível.
- Repeatable (`R__nome.sql`) só para views e funções recriáveis.
- **Flyway Community não tem undo.** O "rollback" é uma nova migration que compensa a anterior.

## 5. Mudanças arriscadas de schema

| Mudança | Forma segura |
|---|---|
| Coluna `NOT NULL` em tabela com dados | Adicionar nullable (ou com `DEFAULT`) → preencher → `SET NOT NULL` |
| Renomear coluna/tabela | Expandir/contrair: criar nova, copiar, código usa as duas, remover antiga numa versão depois |
| Remover coluna | Primeiro tirar do código, remover numa migration posterior |
| Índice em tabela grande | Avisar sobre lock. No Postgres, `CREATE INDEX CONCURRENTLY` não roda dentro de transação: coloque-o sozinho numa migration e use `spring.flyway.postgresql.transactional-lock=false` (no Flyway: `flyway.postgresql.transactional.lock`), senão a migration pode travar |
| Mudar tipo de coluna | Verificar conversão de dados existentes e o tamanho da tabela |

Sempre informe no resumo: risco de perda de dados, lock e se a mudança é reversível.
