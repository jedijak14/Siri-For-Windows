$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null
 $ast=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot '../electron/native/automation.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){$errors | ForEach-Object { Write-Error $_.Message }; exit 1}
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$definitions=$ast.FindAll({param($node) $node -is [System.Management.Automation.Language.StringConstantExpressionAst] -and $node.Value.Contains('public static class SiriNative')},$true)
if($definitions.Count -ne 1){throw 'Expected a single native helper definition.'}
Add-Type -TypeDefinition $definitions[0].Value
Write-Output 'PowerShell syntax, UI Automation assemblies, and native C# helper compilation checked. No interactive app data was read.' 
