import sys; from database_manager import db; from cuatrimestral_supabase_manager import supabase_manager; from infoplazas_tab_module import es_infoplaza_cerrada; local = db.get_control_entrega_local(2026, 2); data, _ = supabase_manager.get_infoplazas_by_regional('Los Santos'); all_infoplazas = [info for info in data if not es_infoplaza_cerrada(info)]; nums = []; ent = [];
for info in all_infoplazas: num = int(info.get('numero', 0)) if str(info.get('numero', '')).isdigit() else 0; estado = local.get(num, {}).get('estado', 'Pendiente'); nums.append(num); 
    if estado == 'Entregado': ent.append(num)
print(f'Total nums: {len(nums)}, Unique nums: {len(set(nums))}'); print(f'Total Entregados: {len(ent)}, Unique Entregados: {len(set(ent))}');
