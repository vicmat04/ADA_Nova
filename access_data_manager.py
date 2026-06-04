
import os
import shutil
import tempfile
import secrets
import time

import os
import shutil
import tempfile
import secrets
import time
import json
import subprocess
import re
import pandas as pd
from datetime import datetime

class AccessDataManager:
    """
    Gestor HÍBRIDO para operaciones con Microsoft Access.
    
    Usa un 'puente' via PowerShell (32-bit) para utilizar el driver 
    'Microsoft.Jet.OLEDB.4.0' nativo de Windows.
    
    ESTO ELIMINA LA NECESIDAD DE INSTALAR:
    - Access Database Engine 2010/2016
    - Drivers ODBC
    - Conflictos de 32/64 bits
    """
    
    # Script de PowerShell incrustado para no depender de archivos externos
    _READ_MDB_SCRIPT = r"""
param (
    [string]$MdbPath,
    [string]$Query,
    [string]$Password
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if (-not (Test-Path $MdbPath)) {
    Write-Error "Archivo no encontrado: $MdbPath"
    exit 1
}

$connStr = "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$MdbPath;Jet OLEDB:Database Password=$Password;"
$conn = New-Object System.Data.OleDb.OleDbConnection($connStr)

try {
    $conn.Open()
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = $Query
    
    $adapter = New-Object System.Data.OleDb.OleDbDataAdapter($cmd)
    $dt = New-Object System.Data.DataTable
    $null = $adapter.Fill($dt)
    
    $data = @()
    foreach ($row in $dt.Rows) {
        $obj = @{}
        foreach ($col in $dt.Columns) {
            $val = $row[$col]
            if ($val -is [DBNull]) {
                $obj[$col.ColumnName] = $null
            } else {
                $obj[$col.ColumnName] = $val
            }
        }
        $data += $obj
    }
    
    $data | ConvertTo-Json -Depth 3 -Compress
    
} catch {
    Write-Error "Error de BD: $_"
    exit 1
} finally {
    if ($conn.State -eq 'Open') { $conn.Close() }
}
"""

    @classmethod
    def _ensure_script(cls):
        """Escribe el script de PowerShell en una carpeta temporal segura."""
        base_dir = os.path.join(tempfile.gettempdir(), "ADA_Bridge")
        os.makedirs(base_dir, exist_ok=True)
        script_path = os.path.join(base_dir, "read_mdb_v1.ps1")
        
        # Reescribir siempre para asegurar integridad
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(cls._READ_MDB_SCRIPT)
            
        return script_path

    @staticmethod
    def _crear_copia_segura(db_path):
        """Crea copia temporal para evitar bloqueos de archivo."""
        base_temp_dir = os.path.join(tempfile.gettempdir(), "ADA_Temp")
        os.makedirs(base_temp_dir, exist_ok=True)
        
        temp_dir = os.path.join(base_temp_dir, f"session_{secrets.token_hex(4)}")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, "temp.mdb")
        
        # print(f"[DB BRIDGE] Copiando: {db_path} -> {temp_path}")
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                shutil.copy2(db_path, temp_path)
                return temp_path
            except Exception as e:
                # print(f"[DB BRIDGE] Error copia {attempt+1}: {e}")
                time.sleep(1)
        
        return None

    @classmethod
    def _execute_bridge_query(cls, db_path, password, query):
        """Ejecuta la consulta via PowerShell 32-bit."""
        
        # 1. Copia segura
        temp_path = cls._crear_copia_segura(db_path)
        if not temp_path:
            return None, "No se pudo copiar el archivo (Lock)"

        # 2. Preparar script
        script_path = cls._ensure_script()
        
        # 3. Invocar PowerShell 32-bit (SysWOW64)
        ps_32 = r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
        
        cmd = [
            ps_32, "-ExecutionPolicy", "Bypass", "-File", script_path,
            "-MdbPath", temp_path,
            "-Query", query,
            "-Password", password if password else ""
        ]
        
        try:
            # print(f"[DB BRIDGE] Ejecutando query...")
            # Forzar codificación correcta para caracteres latinos
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Limpieza inmediata
            try:
                os.remove(temp_path)
                os.rmdir(os.path.dirname(temp_path))
            except: pass

            if result.returncode != 0:
                print(f"[DB BRIDGE] Error STDERR: {result.stderr}")
                return None, f"Error PowerShell: {result.stderr}"
            
            # Parsear JSON response
            output = result.stdout.strip()
            if not output:
                return [], None # Query vacía es un éxito sin datos
                
            data = json.loads(output)
            
            # Convertir a lista si devuelve un solo objeto
            if isinstance(data, dict):
                data = [data]
            elif isinstance(data, list):
                pass
            else:
                data = []
                
            return data, None
            
        except Exception as e:
            print(f"[DB BRIDGE] Excepción subprocess: {e}")
            return None, str(e)

    @staticmethod
    def _parse_dates(data_list, date_columns=['DATETIME']):
        """Convierte fechas formato JSON /Date(123456)/ a objetos datetime reales."""
        if not data_list:
            return pd.DataFrame()
            
        df = pd.DataFrame(data_list)
        
        # Regex para extraer milisegundos: /Date(1557781220000)/
        pattern = re.compile(r"\/Date\((\d+)\)\/")
        
        for col in date_columns:
            if col in df.columns:
                def convert(val):
                    if isinstance(val, str):
                        match = pattern.search(val)
                        if match:
                            ts_ms = int(match.group(1))
                            return datetime.fromtimestamp(ts_ms / 1000.0)
                    return val
                
                df[col] = df[col].apply(convert)
                df[col] = pd.to_datetime(df[col])
                
        return df

    @classmethod
    def obtener_ultimo_usuario(cls, db_path, password):
        """Obtiene el último username registrado."""
        query = "SELECT TOP 1 USERNAME, ID FROM SALES ORDER BY ID DESC"
        data, error = cls._execute_bridge_query(db_path, password, query)
        
        if error or not data:
            return None
            
        return data[0].get('USERNAME')

    @classmethod
    def extraer_datos_rango(cls, db_path, password, start_date, end_date):
        """Extrae dataframe de ventas en un rango de fechas."""
        # Access requiere fechas en formato #MM/DD/YYYY# o YYYY-MM-DD
        # Usaremos string format standard
        
        # Nota: Parametrizar queries en PowerShell es complejo, 
        # así que formateamos el string aqui con cuidado.
        
        # IMPORTANTE: Access SQL usa # para fechas
        q_start = start_date.strftime('%Y-%m-%d %H:%M:%S')
        q_end = end_date.strftime('%Y-%m-%d %H:%M:%S')
        
        query = f"SELECT ID, DATETIME, USERNAME, ITEMNAME FROM SALES WHERE DATETIME BETWEEN #{q_start}# AND #{q_end}# ORDER BY DATETIME DESC"
        
        data_list, error = cls._execute_bridge_query(db_path, password, query)
        
        if error:
            return None, error
            
        df = cls._parse_dates(data_list)
        return df, None

    @classmethod
    def extraer_nuevos_registros(cls, db_path, password, last_id: int):
        """Extrae registros posteriores a un ID dado."""
        # last_id es un entero
        
        # Access syntax
        query = f"SELECT ID, DATETIME, USERNAME, ITEMNAME FROM SALES WHERE ID > {last_id} ORDER BY ID ASC"
        
        data_list, error = cls._execute_bridge_query(db_path, password, query)
        
        if error:
            return None, error
        
        # Si no hay datos, retorna vacío
        if not data_list:
            return pd.DataFrame(), None
            
        df = cls._parse_dates(data_list)
        return df, None

    @classmethod
    def extraer_useraccounts(cls, db_path, password):
        """Extrae todos los nombres de usuario de la tabla USERACCOUNT."""
        query = "SELECT USERNAME FROM USERACCOUNT"
        data, error = cls._execute_bridge_query(db_path, password, query)
        
        if error:
            return None, error
        
        if not data:
            return [], None
        
        usernames = [str(row.get('USERNAME', '')).strip() for row in data if row.get('USERNAME')]
        return usernames, None
