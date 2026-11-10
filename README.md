# ai_agent_springboot

Kit de customização do Claude Code para projetos Spring Boot: uma skill (`spring-boot`), quatro subagentes (`spring-test-writer`, `spring-reviewer`, `spring-migration`, `build-runner`) e dois hooks em Python que travam o que cada agente pode editar e rodar.

```
ai_agent_springboot/
├── spring-claude-kit/
│   ├── claude/            → copiado para ~/.claude/ pelo install.sh
│   │   ├── skills/spring-boot/   SKILL.md, testing.md, persistence.md
│   │   ├── agents/               os 4 subagentes
│   │   └── hooks/                guard-paths.py, bash-allowlist.py
│   ├── templates/CLAUDE.md       modelo de CLAUDE.md por projeto
│   ├── install.sh
│   └── README.md                 documentação completa
└── tests/hooktest.py             suíte dos hooks: python3 tests/hooktest.py
```

## Instalar

Requisitos: Claude Code e `python3`.

```bash
cd spring-claude-kit
bash install.sh
```

O script copia `claude/` para `~/.claude/` e faz backup com data e hora (`<arquivo>.<AAAAMMDD-HHMMSS>.bak`) de qualquer arquivo diferente que já exista.

Desenho, modelos, uso, testes e limites das travas estão em [spring-claude-kit/README.md](spring-claude-kit/README.md).
