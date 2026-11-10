#!/usr/bin/env python3
"""
Suíte dos hooks do kit. Uso, a partir da raiz do repo:

    python3 tests/hooktest.py

Copia claude/hooks/ para um HOME temporário e roda o comando LITERAL do frontmatter de cada agente
(via sh -c e bash -c), com o JSON do PreToolUse no stdin. Nada fora de pastas temporárias é tocado.
Exit 0 se todos os casos batem com o esperado; exit 1 caso contrário.
"""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent / "spring-claude-kit" / "claude"
WORK = Path(tempfile.mkdtemp(prefix="hooktest-"))
HOME = WORK / "home"
shutil.copytree(KIT / "hooks", HOME / ".claude" / "hooks")

# Lê matcher/command do frontmatter (escalares simples, sem PyYAML).
CMDS = {}
for name, short in [("build-runner", "BR"), ("spring-reviewer", "RV"), ("spring-test-writer", "TW"), ("spring-migration", "MG")]:
    front = (KIT / "agents" / f"{name}.md").read_text().split("---")[1]
    pairs = re.findall(r'matcher:\s*"([^"]+)"\s*\n\s*hooks:\s*\n\s*- type: command\s*\n\s*command: (.+)', front)
    assert pairs, f"hooks não encontrados em {name}.md"
    for matcher, command in pairs:
        CMDS[(short, matcher)] = command.strip()

def run(agent, matcher, payload, shell="sh", env=None, raw=None):
    p = subprocess.run([shell, "-c", CMDS[(agent, matcher)]], input=raw if raw is not None else json.dumps(payload),
                       capture_output=True, text=True, env={**os.environ, "HOME": str(HOME), **(env or {})})
    return p.returncode

A, B = 0, 2
ALL = ["BR", "RV", "TW", "MG"]
# (agentes, comando, esperado)
bash = [
    # --- comandos normais de trabalho (falsos positivos) ---
    (["BR", "TW", "MG"], "./mvnw -q -B verify", A),
    (["BR", "TW", "MG"], "./mvnw -q test -Dtest=PedidoServiceTest", A),
    (["BR", "TW", "MG"], "./mvnw -q test -Dtest='PedidoServiceTest#buscar*'", A),
    (["BR", "TW", "MG"], './mvnw -q test -Dtest="PedidoServiceTest#buscar*"', A),
    (["BR", "TW", "MG"], "./mvnw -q test -Dtest='*Repository*' -Dsurefire.failIfNoSpecifiedTests=false", A),
    (["BR", "TW", "MG"], "mvn -q test", A),
    (["BR", "TW", "MG"], "./mvnw -q -B verify 2>&1 | tail -n 50", A),
    (["BR", "TW", "MG"], "./mvnw test | grep -E 'Tests run|FAIL'", A),
    (["BR", "TW", "MG"], './mvnw test 2>&1 | grep -E "Tests run|ERROR"', A),
    (["BR", "TW", "MG"], "./mvnw -q test -pl modulo -am", A),
    (["BR", "TW", "MG"], "MAVEN_OPTS=-Xmx2g ./mvnw -q verify", A),
    (["BR", "TW", "MG"], "./gradlew build --console=plain", A),
    (["BR", "TW", "MG"], "./gradlew test --tests 'PedidoServiceTest.buscar*'", A),
    (["BR", "TW", "MG"], "./gradlew :app:test", A),
    (ALL, "find . -maxdepth 1 -name mvnw -o -maxdepth 1 -name gradlew", A),
    (ALL, "find src -name '*.java' -path '*migration*'", A),
    (ALL, "find . -type f -name '*.sql' | head -20", A),
    (ALL, r"find . \( -name '*.java' -o -name '*.kt' \) -not -path '*/.git/*'", A),
    (ALL, 'find . -name "-exec"', A),
    (ALL, "grep -rn --include='*.java' '@Transactional' src", A),
    (ALL, "grep -rn @Transactional src", A),
    (ALL, 'grep -rn "Transactional(" src', A),
    (ALL, "grep -rn 'foo$' src", A),
    (ALL, "grep -h 'Tests run' target/surefire-reports/*.txt", A),
    (ALL, "grep -rc RestClient src | grep -v ':0' | wc -l", A),
    (["RV", "TW", "MG"], "git status", A),
    (["RV", "TW", "MG"], "git diff HEAD", A),
    (["RV", "TW", "MG"], "git diff HEAD~1 --stat", A),
    (["RV", "TW", "MG"], "git log --oneline -n 5", A),
    (["RV", "TW", "MG"], "git log --format='%h %s'", A),
    (["RV", "TW", "MG"], 'git log --pretty=format:"%h %an %s"', A),
    (["RV", "TW", "MG"], "git show abc123:src/main/java/A.java", A),
    (["RV", "TW", "MG"], "git --no-pager diff", A),
    (["RV", "TW", "MG"], "git -C /a/b diff", A),
    (["RV", "TW", "MG"], "git -C '/a b' diff", A),
    (["RV", "TW", "MG"], "git --no-pager -C '/a b' log -n 3", A),
    (["RV", "TW", "MG"], "git ls-files src/main/resources/db/migration", A),
    (["RV", "TW", "MG"], "git status-x", A),  # \b deixa passar; o git recusa (subcomando inexistente)
    (["RV"], "git diff main...HEAD", A),
    (["RV"], "git merge-base HEAD main", A),
    (["RV"], "git blame -L 10,20 src/A.java", A),
    (["RV"], "git rev-parse --abbrev-ref HEAD", A),
    # --- falsos positivos conhecidos (bloqueia, mas a mensagem orienta) ---
    (["RV"], "git diff HEAD^", B),
    (["MG"], "find src/main/resources/db/migration -name 'V*' | sort", B),
    (["BR"], "./mvnw -Dtest=X#y test", B),
    # --- encadeamento e redirecionamento ---
    (ALL, "git status && git diff", B),
    (ALL, "git status; git diff", B),
    (ALL, "./mvnw test || true", B),
    (ALL, "./mvnw test &", B),
    (ALL, "cd sub && ./mvnw test", B),
    (ALL, "./mvnw test > out.txt", B),
    (ALL, "./mvnw test 2>/dev/null", B),
    (ALL, "./mvnw test 2>&1>out", B),
    (ALL, "grep x < /etc/passwd", B),
    (ALL, "./mvnw test\nrm -rf src", B),
    (ALL, "./mvnw test |", B),
    # --- expansões do shell fora de aspas (regra de caracteres) ---
    (ALL, "find . {-delete,-print}", B),          # expansão de chaves
    (ALL, "find . -name x{,}", B),
    (ALL, "find . $'-delete'", B),                 # $'...'
    (ALL, 'find . $"-delete"', B),                 # $"..."
    (ALL, "find . ${X:--delete}", B),              # ${...}
    (ALL, "find . $X", B),
    (ALL, "grep $(rm -rf x) .", B),                # $(...)
    (ALL, "grep `rm -rf x` .", B),                 # crase
    (ALL, "find . (-delete)", B),                  # parênteses sem escape
    (ALL, "grep x (", B),
    (ALL, "grep x *(e:'rm -rf x':)", B),           # qualificador zsh
    (ALL, 'grep "$(rm -rf x)" .', B),              # aspas duplas com $
    (ALL, 'grep "${HOME}" .', B),
    (ALL, 'grep "`id`" .', B),                     # aspas duplas com crase
    (ALL, 'grep "\\\\$(id)" .', B),                # "\\$(...)": \\ literal e depois $
    (ALL, 'grep "\\$x" .', A),                     # "\$x" é literal
    (ALL, "grep '$(id)' .", A),                    # aspas simples: literal
    (ALL, "grep x [ab]", B),
    (ALL, "grep x !", B),
    (ALL, "grep x # comentario", B),
    (ALL, "grep x \\; ", B),
    (ALL, "grep x\tsrc", B),
    (ALL, "grep 'aberta", B),
    (ALL, "grep x ^y", B),
    (["BR"], r"JAVA_HOME=/j find . \( -name x \)", B),  # \( só vale com find no início do segmento
    (ALL, r"grep x \( y", B),
    # --- find com ações ---
    (ALL, "find . -delete", B),
    (ALL, "find . -name '*.class' -delete", B),
    (ALL, "find . -rm", B),
    (ALL, "find . -exec rm x +", B),
    (ALL, "find . -execdir id +", B),
    (ALL, "find . -ok id +", B),
    (ALL, "find . -fprint out", B),
    (ALL, "find . -fprintf out x", B),
    (ALL, "find . -fls out", B),
    (ALL, r"find . \( -name x \) -delete", B),
    (ALL, "grep -rl x . | find . -delete", B),
    (ALL, "grep -rl x . | xargs rm", B),
    (ALL, "grep -rl x . | sort -o out", B),
    (ALL, "/usr/bin/find . -delete", B),
    # --- comandos fora da lista ---
    (ALL, "rm -rf src", B),
    (ALL, "ls", B),
    (ALL, "cat pom.xml", B),
    (ALL, "sed -i s/a/b/ pom.xml", B),
    (ALL, "python3 -c 1", B),
    (ALL, "bash mvnw test", B),
    (["BR"], "git status", B),
    (["RV"], "./mvnw test", B),
    (["RV", "TW", "MG"], "git push", B),
    (["RV", "TW", "MG"], "git --no-pager push", B),
    (["RV", "TW", "MG"], "git branch -D main", B),
    (["RV", "TW", "MG"], "git checkout -- .", B),
    (["RV", "TW", "MG"], "git reset --hard", B),
    (["RV", "TW", "MG"], "git stash", B),
    (["RV", "TW", "MG"], "git -c core.pager=id diff", B),
    (["RV", "TW", "MG"], "git diff --output=x", B),
    (["RV", "TW", "MG"], "git log -p --output=/tmp/x", B),
    # -C com espaço: o regex não pode voltar atrás e ler ' diff' do caminho como subcomando
    (["RV", "TW", "MG"], "git -C 'a diff' reset --hard", B),
    (["RV", "TW", "MG"], "git -C 'a diff' push", B),
    (["RV", "TW", "MG"], "git -C 'x' push", B),
    (ALL, "PATH=/tmp ./mvnw test", B),
    (ALL, "LD_PRELOAD=x.so grep x .", B),
    (ALL, "MAVEN_OPTS=x", B),
    # --- Maven/Gradle que executam comando ---
    (["BR", "TW", "MG"], "./mvnw exec:exec -Dexec.executable=rm", B),
    (["BR", "TW", "MG"], "./mvnw -D exec.executable=rm test", B),
    (["BR", "TW", "MG"], "mvn antrun:run", B),
    (["BR", "TW", "MG"], "mvn org.codehaus.mojo:exec-maven-plugin:3.1.0:exec", B),
    (["BR", "TW", "MG"], "./gradlew -I init.gradle build", B),
    (["BR", "TW", "MG"], "./gradlew -Iinit.gradle build", B),
    (["BR", "TW", "MG"], "./gradlew --init-script=x build", B),
    (["BR", "TW", "MG"], "./gradlew -Dorg.gradle.jvmargs=-javaagent:x build", B),
    (ALL, "mvnw-evil test", B),
]

fails, total = [], 0
for agents, cmd, exp in bash:
    for ag in agents:
        for sh in ("sh", "bash"):
            total += 1
            rc = run(ag, "Bash", {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(WORK)}, shell=sh)
            if rc != exp:
                fails.append(f"BASH {ag} {sh} esperado={exp} veio={rc}: {cmd!r}")

# --- guard-paths ---
proj = WORK / "proj"
mig = proj / "src/main/resources/db/migration"
mig.mkdir(parents=True)
(proj / "src/test/java").mkdir(parents=True)
(proj / "src/main/java").mkdir(parents=True)
(mig / "V1__init.sql").write_text("x")
(mig / "V2__staged.sql").write_text("x")
g = lambda *a: subprocess.run(["git", "-C", str(proj), "-c", "user.email=a@b", "-c", "user.name=n", *a], capture_output=True, check=True)
g("init", "-q"); g("add", "src/main/resources/db/migration/V1__init.sql"); g("commit", "-qm", "1"); g("add", ".")
(proj / "src/test/java/link").symlink_to(proj / "src/main/java")
outside = WORK / "fora"; outside.mkdir()
(outside / "V1__x.sql").write_text("x")
env = {"CLAUDE_PROJECT_DIR": str(proj)}
guard = [
    ("TW", "Write", proj / "src/test/java/AT.java", A),
    ("TW", "Edit", proj / "modulo/src/test/java/AT.java", A),
    ("TW", "Write", proj / "src/test/resources/application-test.yml", A),
    ("TW", "Write", proj / "src/it/java/AIT.java", A),
    ("TW", "Edit", proj / "src/main/java/A.java", B),
    ("TW", "Edit", proj / "pom.xml", B),
    ("TW", "Edit", proj / "src/test/java/../../main/java/A.java", B),
    ("TW", "Edit", proj / "src/test/java/link/A.java", B),       # symlink para src/main
    ("TW", "Write", WORK / "outro/src/test/java/A.java", B),      # fora do projeto
    ("TW", "Write", "src/test/java/Rel.java", A),                 # relativo ao cwd
    ("MG", "Edit", mig / "V1__init.sql", B),                      # commitada
    ("MG", "Edit", mig / "V2__staged.sql", A),                    # só staged
    ("MG", "Write", mig / "V3__nova.sql", A),
    ("MG", "Write", proj / "src/main/java/db/migration/V4__Java.java", A),
    ("MG", "Write", proj / "outra/pasta/V5__x.sql", A),
    ("MG", "Edit", proj / "src/main/java/Pedido.java", A),
    ("MG", "Edit", outside / "V1__x.sql", B),
    ("MG", "Write", Path("/etc/x"), B),
    ("MG", "Edit", mig / "R__view.sql", A),
]
for ag, tool, path, exp in guard:
    total += 1
    rc = run(ag, "Edit|Write", {"tool_name": tool, "tool_input": {"file_path": str(path)}, "cwd": str(proj)}, env=env)
    if rc != exp:
        fails.append(f"GUARD {ag} esperado={exp} veio={rc}: {path}")
for ag in ("TW", "MG"):
    total += 2
    if run(ag, "Edit|Write", {"tool_name": "Write", "tool_input": {}}, env=env) != B:
        fails.append(f"GUARD {ag} sem file_path deveria bloquear")
    if run(ag, "Edit|Write", None, env=env, raw="lixo") != B:
        fails.append(f"GUARD {ag} JSON inválido deveria bloquear")

shutil.rmtree(WORK, ignore_errors=True)
print(f"{total} casos, {len(fails)} falhas")
print("\n".join(fails))
sys.exit(1 if fails else 0)
