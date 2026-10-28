{
  config,
  pkgs,
  ...
}:

{
  packages = [ pkgs.httpyac ];

  languages.python = {
    enable = true;
    version = "3.14.8";
    uv.enable = true;
    uv.sync.enable = true;
  };

  git-hooks.hooks.mypy.settings.binPath = "${config.env.UV_PROJECT_ENVIRONMENT}/bin/mypy";

  enterTest = ''
    uv run pytest
  '';

  scripts = {
    function_run = {
      description = "Run the function locally (dry-run unless DRY_RUN=false)";
      exec = ''
        uv run functions-framework --source=src/billing_disabler/main.py --target=handle_budget_notification --host=127.0.0.1 --port="''${PORT:-8080}"
      '';
    };
    function_test = {
      description = "Send budget notification scenarios to the local function (interactive unless --all or -n <name> is given)";
      exec = ''
        httpyac send tests/http/budget_notifications.http -o short "$@"
      '';
    };
  };
}
