{ pkgs ? import (builtins.fetchTarball "https://github.com/NixOS/nixpkgs/archive/nixos-unstable.tar.gz") { config.allowUnfree = true; } }:

let
  python = pkgs.python312;

  # Base Python environment
  pythonEnv = python.withPackages (ps: with ps; [
    pip
    setuptools
    wheel
    virtualenv
    huggingface-hub
    jupyterlab
    ipykernel
  ]);

  themeFile = "${pkgs.oh-my-posh}/share/oh-my-posh/themes/agnoster.omp.json";

  zshInit = ''
    # Oh My Posh prompt
    eval "$(${pkgs.oh-my-posh}/bin/oh-my-posh init zsh --config ${themeFile})"

    # fzf
    export FZF_DEFAULT_OPTS="--height=40% --border --info=inline --layout=reverse"
    source ${pkgs.fzf}/share/fzf/key-bindings.zsh
    source ${pkgs.fzf}/share/fzf/completion.zsh

    # zoxide, autosuggestions, syntax highlighting
    eval "$(${pkgs.zoxide}/bin/zoxide init zsh)"
    source ${pkgs.zsh-autosuggestions}/share/zsh-autosuggestions/zsh-autosuggestions.zsh
    source ${pkgs.zsh-syntax-highlighting}/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

    # Nix completions
    fpath=(${pkgs.nix-zsh-completions}/share/zsh/site-functions $fpath)
    autoload -Uz compinit && compinit
  '';

  zshRc = pkgs.writeText "dev-zshrc" zshInit;

in
pkgs.mkShell {
  packages = with pkgs; [
    # Toolchains
    nodejs_22
    corepack
    go
    pythonEnv
    terraform
    google-cloud-sdk

    # JS package managers
    yarn
    pnpm

    # Shell + prompt + helpers
    zsh
    oh-my-posh
    fzf
    zoxide
    zsh-autosuggestions
    zsh-syntax-highlighting
    nix-zsh-completions

    # CLI QoL
    git
    jq
    bat
    fd
    ripgrep

    # System libraries for Python / C++ deps
    stdenv.cc.cc.lib
    zlib

    # Docker
    docker
    docker-compose
  ] ++ pkgs.lib.optionals pkgs.stdenv.isLinux [
    glibc
    gcc-unwrapped.lib
  ];

  GREETING = "Hello, Nix!";

  shellHook = ''
    echo "=== EventAtlas Nix Dev Shell ==="

    ${pkgs.lib.optionalString pkgs.stdenv.isLinux ''
      # Avoid injecting glibc into LD_LIBRARY_PATH; it can destabilize Nix binaries.
      export PROJECT_LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:${pkgs.zlib}/lib"
      export LD_LIBRARY_PATH="$PROJECT_LD_LIBRARY_PATH''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
      export LIBRARY_PATH="$PROJECT_LD_LIBRARY_PATH''${LIBRARY_PATH:+:$LIBRARY_PATH}"
    ''}
    ${pkgs.lib.optionalString pkgs.stdenv.isDarwin ''
      export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:${pkgs.zlib}/lib:''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
      export LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:${pkgs.zlib}/lib:''${LIBRARY_PATH:+:$LIBRARY_PATH}"
    ''}

    # Go workspace
    export GOPATH="$PWD/.gopath"
    export GOBIN="$GOPATH/bin"
    mkdir -p "$GOBIN"
    export PATH="$GOBIN:$PATH"

    # Project directories
    for dir in ; do
      mkdir -p "$dir"
    done

    # Local Python site-packages dir in WSL native filesystem (faster, more space)
    # Use hash of project path to create unique dir per project
    PROJECT_HASH=$(echo "$PWD" | md5sum | cut -d' ' -f1 | cut -c1-8)
    PY_SITE="$HOME/.nix-python-envs/$PROJECT_HASH"
    mkdir -p "$PY_SITE"
    export PYTHONPATH="$PY_SITE:$PYTHONPATH"

    # Use WSL temp dir (native filesystem, not /mnt/d)
    export TMPDIR="/tmp/pip-tmp-$$"
    mkdir -p "$TMPDIR"
    trap "rm -rf $TMPDIR" EXIT

    # Force pip cache to WSL home dir to avoid cross-mount I/O errors and space issues
    export PIP_CACHE_DIR="$HOME/.cache/pip"
    mkdir -p "$PIP_CACHE_DIR"

    REQ_FILE="$PWD/requirements.txt"
    REQ_PREV="$PY_SITE/.requirements.prev"

    # Helper to normalize requirements: drop comments/blank lines, trim trailing spaces
    filter_requirements() {
      grep -Ev '^[[:space:]]*($|#)' "$1" | sed 's/[[:space:]]*$//'
    }

    if [ -f "$REQ_FILE" ]; then
      if [ ! -f "$REQ_PREV" ]; then
        echo "First-time Python deps install into $PY_SITE (WSL native filesystem)"
        echo "----- requirements.txt -----"
        cat "$REQ_FILE"
        echo "----------------------------"

        if python -m pip install --no-cache-dir --no-warn-script-location --target "$PY_SITE" -r "$REQ_FILE"; then
          filter_requirements "$REQ_FILE" > "$REQ_PREV"
          echo "✅ Python packages installed into $PY_SITE"
        else
          echo "⚠️ pip install failed – check the error above (disk space / CUDA, etc.)."
        fi
      else
        CUR_FILTERED="$TMPDIR/requirements.current"
        PREV_SORTED="$TMPDIR/requirements.prev.sorted"
        CUR_SORTED="$TMPDIR/requirements.current.sorted"
        CHANGED_LINES="$TMPDIR/requirements.changed"

        filter_requirements "$REQ_FILE" > "$CUR_FILTERED"
        sort "$CUR_FILTERED" > "$CUR_SORTED"
        sort "$REQ_PREV" > "$PREV_SORTED"

        # Lines present in current but not in previous
        comm -23 "$CUR_SORTED" "$PREV_SORTED" > "$CHANGED_LINES"

        if [ -s "$CHANGED_LINES" ]; then
          echo "Detected changes in requirements.txt, installing these packages:"
          cat "$CHANGED_LINES"

          while IFS= read -r line; do
            [ -z "$line" ] && continue
            echo "pip install $line ..."
            python -m pip install --no-cache-dir --no-warn-script-location --target "$PY_SITE" "$line" || echo "⚠️ Failed to install $line"
          done < "$CHANGED_LINES"

          # Update stored copy
          filter_requirements "$REQ_FILE" > "$REQ_PREV"
          echo "✅ Python deps updated"
        else
          echo "Python deps already up to date (no per-line changes)"
        fi
      fi
    else
      echo "No requirements.txt found – using base pythonEnv only"
    fi

    export PYTHONOPTIMIZE=1

    # Version info (avoid pipeline/pipefail false negatives)
    if command -v node >/dev/null 2>&1; then
      NODE_VERSION="$(node -v 2>/dev/null)"
    else
      NODE_VERSION="missing"
    fi

    if command -v go >/dev/null 2>&1; then
      GO_VERSION="$(go version 2>/dev/null | awk '{print $3}')"
    else
      GO_VERSION="missing"
    fi

    if command -v python >/dev/null 2>&1; then
      PY_VERSION="$(python --version 2>&1)"
    else
      PY_VERSION="missing"
    fi

    if command -v terraform >/dev/null 2>&1; then
      TF_VERSION="$(terraform version -json 2>/dev/null | jq -r '.terraform_version' 2>/dev/null)"
      [ -z "$TF_VERSION" ] && TF_VERSION="missing"
      [ "$TF_VERSION" != "missing" ] && TF_VERSION="v$TF_VERSION"
    else
      TF_VERSION="missing"
    fi

    if command -v gcloud >/dev/null 2>&1; then
      GCLOUD_VERSION="$(gcloud version --format='value(core.version)' 2>/dev/null)"
      [ -z "$GCLOUD_VERSION" ] && GCLOUD_VERSION="missing"
    else
      GCLOUD_VERSION="missing"
    fi

    echo "Node:   $NODE_VERSION"
    echo "Go:     $GO_VERSION"
    echo "Py:     $PY_VERSION"
    echo "TF:     $TF_VERSION"
    echo "gcloud: $GCLOUD_VERSION"

    # Zsh config
    export ZDOTDIR="$PWD/.zsh"
    mkdir -p "$ZDOTDIR"
    cp ${zshRc} "$ZDOTDIR/.zshrc" 2>/dev/null || cat ${zshRc} > "$ZDOTDIR/.zshrc"
    chmod 644 "$ZDOTDIR/.zshrc" 2>/dev/null || true

    # Only switch shells for interactive sessions.
    if [ -n "$PS1" ]; then
      if [ -z "$ZSH_VERSION" ]; then
        exec ${pkgs.zsh}/bin/zsh -l
      else
        source "$ZDOTDIR/.zshrc"
      fi
    fi
  '';
}
