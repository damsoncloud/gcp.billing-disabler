{
  config,
  pkgs,
  ...
}:

let
  port = "\${PORT:-8080}";
in
{
  env.IMAGE = "localhost/billing-disabler:local";

  packages = [
    # keep-sorted start
    pkgs.httpyac
    pkgs.podman
    pkgs.trivy
    # keep-sorted end
  ];

  languages.python = {
    enable = true;
    version = "3.14.8";
    uv.enable = true;
    uv.sync.enable = true;
  };

  enterTest = ''
    uv run pytest
  '';

  scripts = {
    function_run = {
      description = "Run the function locally (dry-run unless DRY_RUN=false)";
      exec = ''
        uv run functions-framework --source=src/billing_disabler/main.py --target=handle_budget_notification --host=127.0.0.1 --port="${port}"
      '';
    };
    version_bump = {
      description = "Set the project version to the latest release tag bumped by <major|minor|patch> and print it";
      exec = ''
        set -euo pipefail
        latest=$(git -C "$DEVENV_ROOT" describe --tags --abbrev=0 --match 'v*' 2>/dev/null || echo v0.0.0)
        uv version "''${latest#v}" --frozen >/dev/null
        uv version --bump "$1" --no-sync --short
      '';
    };
    function_test = {
      description = "Send budget notification scenarios to the local function (interactive unless --all or -n <name> is given)";
      exec = ''
        httpyac send tests/http/budget_notifications.http -o short "$@"
      '';
    };
    image_build = {
      description = "Build the container image";
      exec = ''
        podman build \
          --source-date-epoch "$(git -C "$DEVENV_ROOT" log -1 --format=%ct)" \
          --build-arg PYTHON_VERSION=${config.languages.python.version} \
          --build-arg UV_VERSION=${config.languages.python.uv.package.version} \
          --build-arg VERSION="$(uv version --short)" \
          --build-arg REVISION="$(git -C "$DEVENV_ROOT" rev-parse HEAD)" \
          --tag "$IMAGE" \
          --file "$DEVENV_ROOT/Containerfile" \
          "$DEVENV_ROOT"
      '';
    };
    image_scan = {
      description = "Scan the container image for vulnerabilities, failing on fixable HIGH/CRITICAL ones; optionally write a SARIF report: [sarif-file]";
      exec = ''
        set -euo pipefail
        archive=$(mktemp --suffix=.tar)
        trap 'rm -f "$archive"' EXIT
        podman save --format docker-archive --output "$archive" "$IMAGE"
        if [ -n "''${1:-}" ]; then
          trivy image --input "$archive" --ignore-unfixed --format sarif --output "$1"
        fi
        trivy image --input "$archive" --ignore-unfixed --severity HIGH,CRITICAL --exit-code 1
      '';
    };
    image_push = {
      description = "Push the container image to REGISTRY_IMAGE tagged with the project version, its major.minor, major and latest";
      exec = ''
        set -euo pipefail
        : "''${REGISTRY_IMAGE:?REGISTRY_IMAGE must be set}"
        version=$(uv version --short)
        IFS=. read -r major minor _ <<<"$version"
        for tag in "$version" "$major.$minor" "$major" latest; do
          podman tag "$IMAGE" "$REGISTRY_IMAGE:$tag"
          podman push "$REGISTRY_IMAGE:$tag"
        done
      '';
    };
    image_run = {
      description = "Run the container image locally with ADC mounted if present (dry-run unless DRY_RUN=false)";
      exec = ''
        set -euo pipefail
        port="${port}"
        adc="''${CLOUDSDK_CONFIG:-$HOME/.config/gcloud}/application_default_credentials.json"
        container_adc=/etc/gcloud/adc.json
        adc_args=()
        if [ -f "$adc" ]; then
          # keep-id maps the host user to the image's user, so the credentials file stays readable
          uid=$(podman image inspect --format '{{.Config.User}}' "$IMAGE")
          adc_args=(
            --userns="keep-id:uid=$uid,gid=$uid"
            --volume "$adc:$container_adc:ro"
            --env GOOGLE_APPLICATION_CREDENTIALS="$container_adc"
          )
        fi
        # DRY_RUN is passed only when set, so the function's own default applies otherwise
        exec podman run --rm --publish "127.0.0.1:$port:$port" --env PORT="$port" --env DRY_RUN "''${adc_args[@]}" "$IMAGE"
      '';
    };
    image_test = {
      description = "Run offline budget notification scenarios against the container image, without credentials";
      packages = [ pkgs.curl ];
      exec = ''
        set -euo pipefail
        export PORT="${port}"
        container=$(podman run --detach --rm --publish "127.0.0.1:$PORT:$PORT" --env PORT "$IMAGE")
        trap 'podman stop "$container" >/dev/null' EXIT
        # The port is published before the function listens, so wait for an HTTP response rather than a TCP connection
        for _ in $(seq 1 30); do
          curl --silent --output /dev/null "http://127.0.0.1:$PORT" && break
          sleep 1
        done
        function_test -t offline "$@"
      '';
    };
  };
}
