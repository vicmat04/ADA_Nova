$MdbPath = ".\645.mdb"
$Password = "oNer00FooR3n0"
$Query = "SELECT COUNT(*) as Total, MAX(ID) as MaxID, MIN(ID) as MinID FROM SALES"

try {
    # Usamos Resolve-Path para asegurar que el path es absoluto y correcto para el driver OLEDB
    $AbsPath = (Resolve-Path $MdbPath).Path
    $connStr = "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$AbsPath;Jet OLEDB:Database Password=$Password;"
    $conn = New-Object System.Data.OleDb.OleDbConnection($connStr)
    $conn.Open()
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = $Query
    $adapter = New-Object System.Data.OleDb.OleDbDataAdapter($cmd)
    $dt = New-Object System.Data.DataTable
    $null = $adapter.Fill($dt)
    
    $row = $dt.Rows[0]
    Write-Host "Total: $($row.Total)"
    Write-Host "MaxID: $($row.MaxID)"
    Write-Host "MinID: $($row.MinID)"
    $conn.Close()
} catch {
    Write-Error "Error: $_"
}
