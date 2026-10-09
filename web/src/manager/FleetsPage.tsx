"use client";
import { useState, type FormEvent } from "react";
import { Button } from "@/ui";
import { api } from "./api";
import { Confirm, Empty, Errors, Field, Overview, PageTitle, Search } from "./components";
import { useEntities } from "./useEntities";
import type { Entity, Fleet, VehicleType } from "./types";
import s from "./manager.module.css";
import { Dropdown } from "./Dropdown";
import { FormModal } from "./FormModal";
import { LoadingState } from "./LoadingState";
import { Skeleton } from "@/components/ui/skeleton";

export default function FleetsPage() {
  const types = useEntities<VehicleType>("vehicle-types"), fleets = useEntities<Fleet>("fleets");
  const [tab,setTab] = useState<"types"|"fleets">("types");
  const [editor,setEditor] = useState<{ id?: number; kind: "types"|"fleets"; base: VehicleType|Fleet }|null>(null);
  const [error,setError] = useState<unknown>(null), [busy,setBusy] = useState(false);
  const [search,setSearch] = useState("");
  const [deleting,setDeleting] = useState<{ id:number; name:string; kind:"types"|"fleets" }|null>(null);
  async function save(spec: VehicleType|Fleet) {
    if (!editor) return;
    if(!spec.name.trim()){setError(new Error("Tên không được để trống."));return;}
    setBusy(true); setError(null);
    try { if(editor.kind==="types") await api.save("vehicle-types",spec as VehicleType,editor.id); else await api.save("fleets",spec as Fleet,editor.id); setEditor(null); await Promise.all([types.reload(),fleets.reload()]); }
    catch(e){setError(e);} finally {setBusy(false);}
  }
  async function remove() {
    if(!deleting)return;
    const d=deleting;setDeleting(null);setBusy(true);setError(null);
    try {await api.remove(d.kind==="types"?"vehicle-types":"fleets",d.id);await Promise.all([types.reload(),fleets.reload()]);}
    catch(e){setError(e);} finally {setBusy(false);}
  }
  const list = tab==="types"?types:fleets;
  const matches=(name:string)=>name.toLocaleLowerCase("vi").includes(search.trim().toLocaleLowerCase("vi"));
  const filteredTypes=types.items.filter(e=>matches(e.name)),filteredFleets=fleets.items.filter(e=>matches(e.name));
  return <main className={s.page}>
    <PageTitle eyebrow="NGUỒN LỰC VẬN HÀNH" title="Đội xe & loại xe" description="Quản lý cấu hình phương tiện và quy mô đội xe cho các thử nghiệm." action={<Button variant="primary" disabled={busy} onClick={()=>{setError(null);setEditor({kind:tab,base:tab==="types"?{name:"",group:"car",seats:4,range_km:null}:{name:"",composition:[]}});}}>+ {tab==="types"?"Thêm loại xe":"Thêm fleet"}</Button>}/>
    <Overview items={[
      {label:"Loại xe",loading:types.loading,value:types.error?"—":types.items.length,hint:"Danh mục ô tô và xe máy",icon:"car"},
      {label:"Đội xe",loading:fleets.loading,value:fleets.error?"—":fleets.items.length,hint:"Các nhóm phương tiện đã cấu hình",icon:"scenario"},
      {label:"Tổng xe cấu hình",loading:fleets.loading,value:fleets.error?"—":fleets.items.reduce((n,f)=>n+f.spec.composition.reduce((sum,c)=>sum+c.count,0),0).toLocaleString("vi-VN"),hint:"Tổng thành phần trong các đội xe đã lưu",icon:"chart"},
    ]}/>
    <div className={s.toolbar}><div className={s.tabs} role="tablist" aria-label="Cấu hình fleet">
      <button role="tab" aria-selected={tab==="types"} disabled={!!editor} onClick={()=>setTab("types")}>Loại xe ({types.loading?<Skeleton className="workspace-skeleton inline-block h-3 w-4"/>:types.error?"—":types.items.length})</button>
      <button role="tab" aria-selected={tab==="fleets"} disabled={!!editor} onClick={()=>setTab("fleets")}>Fleet ({fleets.loading?<Skeleton className="workspace-skeleton inline-block h-3 w-4"/>:fleets.error?"—":fleets.items.length})</button>
    </div><Button size="sm" disabled={busy} onClick={()=>void Promise.all([types.reload(),fleets.reload()])}>Làm mới</Button></div>
    <Errors error={editor?null:error||types.error||fleets.error}/>
    {list.items.length>0&&<div className={s.toolbar}><Search label="Tìm loại xe hoặc đội xe…" value={search} onChange={setSearch}/><span className={s.resultCount}>{tab==="types"?filteredTypes.length:filteredFleets.length} kết quả</span></div>}
    {list.loading ? <LoadingState label="Đang tải cấu hình đội xe"/> : !list.items.length ? <Empty>Chưa có {tab==="types"?"loại xe":"fleet"}. Thêm cấu hình đầu tiên để bắt đầu.</Empty> :
      !(tab==="types"?filteredTypes:filteredFleets).length ? <Empty>Không tìm thấy cấu hình. Thử tên khác hoặc xoá nội dung tìm kiếm.</Empty> :
      <div className={s.tableWrap}><table className={s.table}><thead><tr><th>Tên</th><th>{tab==="types"?"Nhóm / Số chỗ":"Thành phần"}</th><th>{tab==="types"?"Quãng đường tối đa":"Tổng xe"}</th><th>Thao tác</th></tr></thead><tbody>
        {tab==="types"?filteredTypes.map(e=><tr key={e.id}><td><strong>{e.name}</strong></td><td>{e.spec.group==="bike"?"Xe máy":"Ô tô"} · {e.spec.seats} chỗ</td><td>{e.spec.range_km??"—"}{e.spec.range_km!=null?" km":""}</td><td><div className={s.actions}><Button size="sm" aria-label={"Sửa "+e.name} onClick={()=>{setError(null);setEditor({kind:"types",id:e.id,base:e.spec});}}>Sửa</Button><Button size="sm" variant="ghost" className={s.danger} disabled={busy} aria-label={"Xoá "+e.name} onClick={()=>setDeleting({...e,kind:"types"})}>Xoá</Button></div></td></tr>):
        filteredFleets.map(e=><tr key={e.id}><td><strong>{e.name}</strong></td><td>{e.spec.composition.map(c=>c.vehicle_type+" × "+c.count).join(" · ")}</td><td>{e.spec.composition.reduce((a,c)=>a+c.count,0).toLocaleString("vi-VN")}</td><td><div className={s.actions}><Button size="sm" aria-label={"Sửa "+e.name} onClick={()=>{setError(null);setEditor({kind:"fleets",id:e.id,base:e.spec});}}>Sửa</Button><Button size="sm" variant="ghost" className={s.danger} disabled={busy} aria-label={"Xoá "+e.name} onClick={()=>setDeleting({...e,kind:"fleets"})}>Xoá</Button></div></td></tr>)}
      </tbody></table></div>}
    <p className={s.notice}>Quãng đường tối đa được lưu trong cấu hình. Mô hình pin và sạc chưa được áp dụng vào mô phỏng ở giai đoạn này.</p>
    {editor&&<FormModal title={editor.kind==="types"?(editor.id?"Chỉnh sửa loại xe":"Thêm loại xe"):(editor.id?"Chỉnh sửa đội xe":"Thêm đội xe")} description="Lưu cấu hình phương tiện để dùng trong các kịch bản mô phỏng." busy={busy} onClose={()=>{setEditor(null);setError(null);}}>
      <Errors error={error}/>
      {editor.kind==="types"?<VehicleForm key={editor.id??"new-type"} base={editor.base as VehicleType} error={error} busy={busy} onSave={save} onCancel={()=>{setEditor(null);setError(null);}}/>:
      <FleetForm key={editor.id??"new-fleet"} base={editor.base as Fleet} types={types.items} error={error} busy={busy} onSave={save} onCancel={()=>{setEditor(null);setError(null);}}/>}
    </FormModal>}
    {deleting&&<Confirm name={deleting.name} busy={busy} onCancel={()=>setDeleting(null)} onConfirm={()=>void remove()}/>}
  </main>;
}
function VehicleForm({base,error,busy,onSave,onCancel}:{base:VehicleType;error:unknown;busy:boolean;onSave:(v:VehicleType)=>void;onCancel:()=>void}) {
  const [name,setName]=useState(base.name),[group,setGroup]=useState(base.group),[seats,setSeats]=useState(String(base.seats)),[range,setRange]=useState(base.range_km==null?"":String(base.range_km));
  return <form className={s.card+" "+s.form} onSubmit={(e:FormEvent)=>{e.preventDefault();onSave({...base,name:name.trim(),group,seats:Number(seats),range_km:range===""?null:Number(range)});}}>
    <h2>Thông tin loại xe</h2><div className={s.formGrid}>
      <Field label="Tên loại xe" error={error} path="name"><input required value={name} onChange={e=>setName(e.target.value)}/></Field>
      <Field label="Nhóm xe" error={error} path="group"><Dropdown value={group} onValueChange={value=>setGroup(value as VehicleType["group"])}><option value="car">Ô tô</option><option value="bike">Xe máy</option></Dropdown></Field>
      <Field label="Số chỗ" error={error} path="seats"><input type="number" min="1" step="1" required value={seats} onChange={e=>setSeats(e.target.value)}/></Field>
      <Field label="Quãng đường tối đa (km)" hint="Có thể để trống; chưa dùng để tính pin." error={error} path="range_km"><input type="number" min="0.1" step="any" value={range} onChange={e=>setRange(e.target.value)}/></Field>
    </div><div className={s.actions} style={{marginTop:24}}><Button type="submit" variant="primary" disabled={busy}>{busy?"Đang lưu…":"Lưu loại xe"}</Button><Button disabled={busy} onClick={onCancel}>Đóng form</Button></div>
  </form>;
}
function FleetForm({base,types,error,busy,onSave,onCancel}:{base:Fleet;types:Entity<VehicleType>[];error:unknown;busy:boolean;onSave:(v:Fleet)=>void;onCancel:()=>void}) {
  const [name,setName]=useState(base.name),[composition,setComposition]=useState(base.composition.map(c=>({...c,count:String(c.count)})));
  const patch=(i:number,p:Partial<(typeof composition)[number]>)=>setComposition(cs=>cs.map((c,j)=>j===i?{...c,...p}:c));
  return <form className={s.card+" "+s.form} onSubmit={e=>{e.preventDefault();onSave({...base,name:name.trim(),composition:composition.map(c=>({...c,count:Number(c.count)}))});}}>
    <h2>Thông tin fleet</h2><Field label="Tên fleet" error={error} path="name"><input required value={name} onChange={e=>setName(e.target.value)}/></Field>
    <fieldset><legend>Thành phần đội xe</legend>
      {!types.length&&<p className={s.warning}>Thêm loại xe trước khi tạo fleet.</p>}
      {composition.map((c,i)=><div className={s.row} key={i}>
        <Field label={"Loại xe "+(i+1)} error={error} path={"composition["+i+"].vehicle_type"}><Dropdown required value={c.vehicle_type} onValueChange={value=>patch(i,{vehicle_type:value})}><option value="">Chọn loại xe</option>{!types.some(t=>t.name===c.vehicle_type)&&c.vehicle_type&&<option>{c.vehicle_type}</option>}{types.map(t=><option key={t.id} value={t.name}>{t.name}</option>)}</Dropdown></Field>
        <Field label={"Số lượng "+(i+1)} error={error} path={"composition["+i+"].count"}><input type="number" min="1" step="1" required value={c.count} onChange={e=>patch(i,{count:e.target.value})}/></Field>
        <Button onClick={()=>setComposition(cs=>cs.filter((_,j)=>j!==i))}>Bỏ dòng {i+1}</Button>
      </div>)}<Button disabled={!types.length} onClick={()=>setComposition(cs=>[...cs,{vehicle_type:types[0]?.name??"",count:"1"}])}>+ Thêm thành phần</Button>
    </fieldset><div className={s.actions}><Button type="submit" variant="primary" disabled={busy||!composition.length}>{busy?"Đang lưu…":"Lưu fleet"}</Button><Button disabled={busy} onClick={onCancel}>Đóng form</Button></div>
  </form>;
}
