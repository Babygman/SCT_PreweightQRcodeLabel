$devices = Get-CimInstance Win32_PnPEntity | Where-Object {
    $_.PNPDeviceID -match 'VID_0403&PID_6001'
}

$devices | ForEach-Object {
    $comPort = if ($_.Name -match '\((COM\d+)\)') { $Matches[1] } else { $null }
    $serial = ($_.PNPDeviceID -split '\\')[-1]
    [PSCustomObject]@{
        Name = $_.Name
        COMPort = $comPort
        PNPDeviceID = $_.PNPDeviceID
        VID = '0403'
        PID = '6001'
        USBSerial = $serial
        Status = $_.Status
    }
} | Format-Table -AutoSize
