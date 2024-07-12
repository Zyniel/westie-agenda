<#
  .SYNOPSIS
  Convert SVG files into PNG files.
  
  .DESCRIPTION
  This script converts all SVG files from a folder to PNG files.
  Mainly used to convert and compress tiles.
  
  .PARAMETER Folder
  The text to write to the file.

  .PARAMETER ExecPath
  Path to inkscape.exe

  .EXAMPLE
  svg-to-png.ps1 -Folder I:\git\westie-agenda\westie-agenda\images\tiles -ExecPath "inkscape.exe"
#>
[CmdletBinding()]
param (
  [Parameter(Mandatory = $true, HelpMessage = 'Input folder.')]
  [string] $Folder,
  
  [Parameter(Mandatory = $false, HelpMessage = 'Inkspace executable path.')]
  [string] $ExecPath = "inkscape.exe"
)

process {

	Get-ChildItem $Folder -Filter *.svg | 
	Foreach-Object {

        Write-Information "Converting: $($_.Name)"

		# Define the output PNG file path
		$outputFilePath = [System.IO.Path]::ChangeExtension($_.FullName, ".png")

		# Run Inkscape CLI to convert SVG to PNG with max width of 1080px
		& "$ExecPath" $_.FullName --export-filename=$outputFilePath --export-type=png --export-width=720

	}
}

begin {
  # DEFINE FUNCTIONS HERE AND DELETE THIS COMMENT.

  $InformationPreference = 'Continue'
  # $VerbosePreference = 'Continue' # Uncomment this line if you want to see verbose messages.

  # Log all script output to a file for easy reference later if needed.
  [string] $lastRunLogFilePath = "$PSCommandPath.LastRun.log"
  Start-Transcript -Path $lastRunLogFilePath

  # Display the time that this script started running.
  [DateTime] $startTime = Get-Date
  Write-Information "Starting script at '$($startTime.ToString('u'))'."
}

end {
  # Display the time that this script finished running, and how long it took to run.
  [DateTime] $finishTime = Get-Date
  [TimeSpan] $elapsedTime = $finishTime - $startTime
  Write-Information "Finished script at '$($finishTime.ToString('u'))'. Took '$elapsedTime' to run."

  Stop-Transcript
}