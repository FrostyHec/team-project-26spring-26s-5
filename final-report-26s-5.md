# Team Report

> Team ID: 26s-5

## Metrics

1. Preparation

```bash
sudo apt update
sudo apt install cloc -y
pip install radon
```

2. Calculation

```bash
cloc .  # Lines of code + number of source files
radon cc . -a | grep Average  # Cyclomatic complexity
pnpm list | wc -l  # Number of direct dependencies
pnpm ls --depth | grep '@' | wc -l  # Number of all dependencies
```

3. Results

- `cloc`: Lines of code + number of source files

```plain
❯ cloc .
     338 text files.
     338 unique files.
      11 files ignored.

github.com/AlDanial/cloc v 1.90  T=7.65 s (42.8 files/s, 8840.7 lines/s)
-------------------------------------------------------------------------------
Language                     files          blank        comment           code
-------------------------------------------------------------------------------
Python                         137           4952           4676          20039
Markdown                        67           3056              0           8988
TypeScript                      50           1207            817           8311
Vuejs Component                 44            684            473           6839
YAML                             9           1250             79           4679
JSON                            14              8              0           1001
Bourne Shell                     2             50             41            271
TOML                             2             17              0             98
CSS                              1              6              3             47
HTML                             1              0              0             13
-------------------------------------------------------------------------------
SUM:                           327          11230           6089          50286
-------------------------------------------------------------------------------
```

- `radon`: Cyclomatic complexity

```plain
❯ radon cc . -a | grep Average
Average complexity: A (3.1086567164179106)
```

- `pnpm`: Number of dependencies

```plain
❯ pnpm list | wc -l
47
❯ pnpm ls --depth | grep '@' | wc -l
275
```

4. Summary

- Code scale: The project contains 327 source files with 50286 lines of valid code. Python is the main programming language, supplemented by TypeScript and Vue components.
- Code complexity: The average cyclomatic complexity is 3.11 at grade A, showing clear logic and good maintainability.
- Dependency status: It has 47 direct dependencies and 275 total dependencies including transitive ones, with a reasonable dependency volume.