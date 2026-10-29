{
  config,
  pkgs,
  ...
}:

{
  packages = [ pkgs.httpyac ];

  languages.python.enable = true;

  dcp.containerImage = {
    enable = true;
    smokeTest = "function_test -t offline";
    run.passEnv = [ "DRY_RUN" ];
  };

  enterTest = ''
    uv run pytest
  '';

  scripts = {
    function_run = {
      description = "Run the function locally (dry-run unless DRY_RUN=false)";
      exec = ''
        uv run functions-framework --source=src/billing_disabler/main.py --target=handle_budget_notification --host=127.0.0.1 \
          --port="''${PORT:-${toString config.dcp.containerImage.port}}"
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
