# CLI Help

Command line usage:

``` console
$ paasify2 --help
                                                                              
 Usage: paasify2 [OPTIONS] COMMAND [ARGS]...                                  
                                                                              
 Paasify, build your compose-files                                            
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --verbose             -v      INTEGER RANGE          [default: 0]          │
│                               [0<=x<=5]                                    │
│ --config              -c      TEXT                   Path of paasify.yml   │
│                                                      configuration file.   │
│                                                      [env var:             │
│                                                      PAASIFY_PROJECT_DIR]  │
│                                                      [default:             │
│                                                      /home/jez/volumes/da… │
│ --collections_dir     -l      PATH                   Path of paasify       │
│                                                      collections           │
│                                                      directory.            │
│                                                      [env var:             │
│                                                      PAASIFY_COLLECTIONS_… │
│                                                      [default:             │
│                                                      /home/jez/.config/pa… │
│ --install-completion                                 Install completion    │
│                                                      for the current       │
│                                                      shell.                │
│ --show-completion                                    Show completion for   │
│                                                      the current shell, to │
│                                                      copy it or customize  │
│                                                      the installation.     │
│ --help                                               Show this message and │
│                                                      exit.                 │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────╮
│ apply          Build and apply stack                                       │
│ build          Build docker-files                                          │
│ down           Stop docker stack                                           │
│ help           Show this help message                                      │
│ info           Show context infos                                          │
│ init           Create new project/namespace                                │
│ logs           Show stack logs                                             │
│ ls             List all stacks                                             │
│ ps             Show docker stack instances                                 │
│ recreate       Stop, rebuild and create stack                              │
│ reset          Reset presistent application volume data (destructive!)     │
│ schema         Show paasify configurations schema format                   │
│ src-install    Install sources                                             │
│ src-ls         List sources                                                │
│ src-tree       Show source tree                                            │
│ src-update     Update sources                                              │
│ up             Start docker stack                                          │
╰────────────────────────────────────────────────────────────────────────────╯



```