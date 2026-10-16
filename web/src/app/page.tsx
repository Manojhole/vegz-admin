"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type Row = Record<string, unknown>;
type Tab = "dashboard" | "shops" | "agents" | "products" | "orders" | "customers" | "settings" | "audit" | "admins";
type Admin = { id?: number; email?: string; full_name?: string; role?: string };
const API_BASE = (process.env.NEXT_PUBLIC_VEGZ_ADMIN_API_URL || "http://localhost:8000").replace(/\/$/, "");
const TAB_LABELS: Record<Tab, string> = {
 dashboard:"Dashboard", shops:"Shops", agents:"Delivery agents", products:"Product moderation",
 orders:"Orders", customers:"Customers", settings:"Settings", audit:"Audit trail", admins:"Admin access"
};
const ENDPOINTS: Partial<Record<Tab,string>> = {
 shops:"/api/shops", agents:"/api/agents", products:"/api/products", orders:"/api/orders",
 customers:"/api/customers", settings:"/api/settings", audit:"/api/audit?limit=200", admins:"/api/admin-users"
};
const TRANSITIONS: Record<string,string[]> = {
 placed:["confirmed","cancelled"], confirmed:["preparing","cancelled"],
 preparing:["ready_for_pickup","cancelled"], ready_for_pickup:["assigned","cancelled"],
 assigned:["picked_up","cancelled"], picked_up:["out_for_delivery","cancelled"],
 out_for_delivery:["delivered","delivery_failed"], delivered:["refunded"]
};
async function api<T>(path:string, token:string, init:RequestInit={}):Promise<T>{
 const response=await fetch(API_BASE+path,{...init,headers:{"Content-Type":"application/json",...(token?{Authorization:"Bearer "+token}:{}),...(init.headers||{})}});
 const data=await response.json().catch(()=>({} as Row));
 if(!response.ok)throw new Error(String((data as Row).detail||"Request failed ("+response.status+")"));
 return data as T;
}
function value(row:Row,...keys:string[]){for(const key of keys){const v=row[key];if(v!==undefined&&v!==null&&String(v)!=="")return String(v)}return "—"}
function titleFor(tab:Tab,row:Row){return value(row,...(tab==="shops"?["name","shop_name"]:tab==="agents"?["full_name","name"]:tab==="products"?["name","product_name"]:tab==="orders"?["public_code","tracking_code","code"]:tab==="customers"?["full_name","name","phone"]:tab==="admins"?["full_name","email"]:tab==="audit"?["action","entity_type"]:["key","name","id"]))}
function statusFor(row:Row){return value(row,"status","approval_status","payment_status","is_active")}

export default function AdminHomePage(){
 const [token,setToken]=useState("");
 const [admin,setAdmin]=useState<Admin|null>(null);
 const [tab,setTab]=useState<Tab>("dashboard");
 const [dashboard,setDashboard]=useState<Row|null>(null);
 const [records,setRecords]=useState<Partial<Record<Tab,Row[]>>>({});
 const [email,setEmail]=useState("admin@vegz.com");
 const [password,setPassword]=useState("");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const [settingEdits,setSettingEdits]=useState<Record<string,string>>({});

 const refreshDashboard=useCallback(async(session:string)=>{
  const result=await api<Row>("/api/dashboard",session);
  setDashboard(result);
 },[]);
 const loadTab=useCallback(async(session:string,next:Tab)=>{
  const endpoint=ENDPOINTS[next];if(!endpoint)return;
  const result=await api<unknown>(endpoint,session);
  const rows=Array.isArray(result)?result:((result as Row)?.items as Row[]||[]);
  setRecords(old=>({...old,[next]:rows}));
  if(next==="settings"){
    const edits:Record<string,string>={};
    for(const row of rows)edits[String(row.key??row.id)]=String(row.value??"");
    setSettingEdits(edits);
  }
 },[]);

 const signOut=useCallback(()=>{
  if(typeof window!=="undefined")window.localStorage.removeItem("vegz-admin-token");
  setToken("");setAdmin(null);setDashboard(null);setRecords({});setTab("dashboard");
 },[]);

 const startSession=useCallback(async(session:string)=>{
  const me=await api<Admin>("/api/auth/me",session);
  setAdmin(me);setToken(session);
  await refreshDashboard(session);
 },[refreshDashboard]);

 useEffect(()=>{
  const saved=window.localStorage.getItem("vegz-admin-token");
  if(!saved)return;
  void startSession(saved).catch(()=>signOut());
 },[startSession,signOut]);

 useEffect(()=>{
  if(!token||tab==="dashboard")return;
  void loadTab(token,tab).catch(e=>setError(e instanceof Error?e.message:"Could not load this section."));
 },[token,tab,loadTab]);

 async function login(event:React.FormEvent<HTMLFormElement>){
  event.preventDefault();setBusy(true);setError("");
  try{
   const result=await api<{access_token:string;admin:Admin}>("/api/auth/login","",{method:"POST",body:JSON.stringify({email,password})});
   window.localStorage.setItem("vegz-admin-token",result.access_token);
   setToken(result.access_token);setAdmin(result.admin);setPassword("");setTab("dashboard");
   await refreshDashboard(result.access_token);
  }catch(e){setError(e instanceof Error?e.message:"Sign-in failed.")}
  finally{setBusy(false);}
 }

 async function reload(){
  if(!token)return;setBusy(true);setError("");
  try{if(tab==="dashboard")await refreshDashboard(token);else await loadTab(token,tab);await refreshDashboard(token);}
  catch(e){setError(e instanceof Error?e.message:"Refresh failed.");}
  finally{setBusy(false);}
 }

 async function updateStatus(kind:"shops"|"agents"|"products",row:Row,status:string){
  if(!token)return;setBusy(true);setError("");setNotice("");
  try{
   await api(`/api/${kind}/${row.id}`,token,{method:"PATCH",body:JSON.stringify({status})});
   await loadTab(token,kind);await refreshDashboard(token);
   setNotice(`${titleFor(kind,row)} updated to ${status.replaceAll("_"," ")}.`);
  }catch(e){setError(e instanceof Error?e.message:"Could not update status.");}
  finally{setBusy(false);}
 }

 async function updateCustomer(row:Row,status:string){
  if(!token)return;setBusy(true);setError("");setNotice("");
  try{
   await api(`/api/customers/${row.id}`,token,{method:"PATCH",body:JSON.stringify({status})});
   await loadTab(token,"customers");setNotice("Customer status updated.");
  }catch(e){setError(e instanceof Error?e.message:"Could not update customer.");}
  finally{setBusy(false);}
 }

 async function changeOrder(row:Row,status:string){
  if(!token)return;setBusy(true);setError("");setNotice("");
  try{
   await api(`/api/orders/${row.id}/status`,token,{method:"PATCH",body:JSON.stringify({status})});
   await loadTab(token,"orders");await refreshDashboard(token);setNotice("Order status updated.");
  }catch(e){setError(e instanceof Error?e.message:"Could not update order.");}
  finally{setBusy(false);}
 }

 async function setSetting(key:string){
  if(!token)return;setBusy(true);setError("");setNotice("");
  try{
   await api(`/api/settings/${encodeURIComponent(key)}`,token,{method:"PATCH",body:JSON.stringify({value:settingEdits[key]??""})});
   await loadTab(token,"settings");setNotice("Setting saved.");
  }catch(e){setError(e instanceof Error?e.message:"Could not save setting.");}
  finally{setBusy(false);}
 }

 async function toggleAdmin(row:Row){
  if(!token)return;setBusy(true);setError("");setNotice("");
  try{
   await api(`/api/admin-users/${row.id}/active`,token,{method:"PATCH",body:JSON.stringify({is_active:!Boolean(row.is_active)})});
   await loadTab(token,"admins");setNotice("Admin account updated.");
  }catch(e){setError(e instanceof Error?e.message:"Could not update admin.");}
  finally{setBusy(false);}
 }

 const metrics=useMemo(()=>{
  const root=dashboard||{}, raw=(root.metrics&&typeof root.metrics==="object"?root.metrics:{}) as Row;
  const candidates: [string, string[]][]=[["Today’s sales",["gross_sales_today","sales_today","today_sales"]],["Orders today",["orders_today","today_orders"]],["Active orders",["active_orders","active_count"]],["Pending shops",["pending_shops"]],["Pending agents",["pending_agents"]]];
  return candidates.map(([label,keys])=>({label:String(label),number:keys.map(k=>raw[k]).find(v=>v!==undefined&&v!==null)??root[keys[0] as string]??"—"}));
 },[dashboard]);

 if(!token||!admin){
  return <main className="admin-shell"><header className="admin-header"><a className="brand" href="/"><span className="brand-mark">V</span>vegz<span className="brand-dot">.</span></a><span className="header-label">PLATFORM OPERATIONS</span></header>
   <section className="admin-login"><div className="login-intro"><p className="eyebrow">VEGZ CONTROL CENTER</p><h1>Run every store.<br/><span>Keep every order moving.</span></h1><p>Review partner applications, moderate the catalog and follow order operations from one workspace.</p><div className="feature-line"><span>✓</span> Shop & agent approvals <span>✓</span> Orders <span>✓</span> Audit trail</div></div>
    <form className="login-card" onSubmit={login}><div className="login-card-mark">V</div><h2>Admin sign in</h2><p>Use the administrator account configured for this environment.</p><label>Email</label><input type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)}/><label>Password</label><input type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/>{error&&<p className="error-message">{error}</p>}<button className="action-primary" disabled={busy}>{busy?"Signing in…":"Sign in securely →"}</button><small>For security, there is no public admin registration.</small></form>
   </section><footer className="admin-footer">VEGZ · OPERATIONS WORKSPACE</footer></main>;
 }

 const isSuperAdmin=admin.role==="super_admin"||admin.role==="super-admin";
 const rows=records[tab]||[];
 return <main className="admin-shell">
  <header className="admin-header"><a className="brand" href="#"><span className="brand-mark">V</span>vegz<span className="brand-dot">.</span></a><span className="header-label">OPERATIONS CONTROL</span><div className="admin-user"><span className="user-avatar">{(admin.full_name||admin.email||"A").slice(0,1).toUpperCase()}</span><div><strong>{admin.full_name||"Platform administrator"}</strong><small>{admin.role||"admin"} · {admin.email}</small></div><button className="text-button" onClick={signOut}>Sign out</button></div></header>
  <div className="admin-layout"><aside className="admin-nav"><p className="nav-label">WORKSPACE</p>{(["dashboard","orders","shops","agents","products","customers","settings","audit",...(isSuperAdmin?["admins" as Tab]:[])] as Tab[]).map(item=><button key={item} className={tab===item?"nav-button active":"nav-button"} onClick={()=>{setError("");setNotice("");setTab(item);}}><span>{({dashboard:"▦",orders:"▣",shops:"⌂",agents:"♧",products:"▤",customers:"♙",settings:"⚙",audit:"☷",admins:"◎"})[item]}</span>{TAB_LABELS[item]}{item==="shops"&&records.shops&&<small>{records.shops.filter(r=>statusFor(r)==="pending").length}</small>}</button>)}<div className="nav-note"><span>✦</span><strong>Operate with confidence</strong><p>Use explicit state changes and keep partner approvals auditable.</p></div></aside>
   <section className="admin-main"><div className="page-heading"><div><p className="eyebrow">VEGZ PLATFORM / {TAB_LABELS[tab].toUpperCase()}</p><h1>{tab==="dashboard"?"Platform overview":TAB_LABELS[tab]}</h1><p>{tab==="dashboard"?"A snapshot of partner and order operations.":tab==="shops"?"Review vegetable and grocery shop applications.":tab==="agents"?"Approve delivery partners before they go online.":tab==="products"?"Moderate listings before exposing them to customers.":tab==="orders"?"Review order records and advance valid order states.":tab==="customers"?"Review customer accounts and access status.":tab==="settings"?"Manage platform settings stored by the admin service.":tab==="audit"?"Review recorded admin operations.":"Manage administrators."}</p></div><button className="refresh-button" onClick={()=>void reload()} disabled={busy}>{busy?"Loading…":"↻ Refresh"}</button></div>
    {error&&<div className="alert error">{error}</div>}{notice&&<div className="alert success">{notice}</div>}
    {tab==="dashboard"?<><div className="metric-grid">{metrics.map(metric=><article className="metric-card" key={metric.label}><span>{metric.label}</span><strong>{typeof metric.number==="number"?metric.number.toLocaleString():String(metric.number)}</strong><small>Admin service records</small></article>)}</div><div className="panel"><div className="panel-heading"><div><h2>Quick actions</h2><p>Review queues and current operational records.</p></div></div><div className="quick-grid">{(["shops","agents","products","orders"] as Tab[]).map(key=><button key={key} onClick={()=>setTab(key)} className="quick-card"><span>{({shops:"⌂",agents:"♧",products:"▤",orders:"▣"})[key]}</span><strong>{TAB_LABELS[key]}</strong><small>Open workspace →</small></button>)}</div></div><div className="alert info"><strong>Integration note:</strong> some admin-managed records are separate from customer/shop/agent service records. Validate cross-service approval and status callbacks before launch.</div></>
    :tab==="settings"?<div className="record-list">{rows.length===0?<Empty/>:rows.map(row=><article className="record-card" key={String(row.id??row.key)}><div className="record-icon">⚙</div><div className="record-body"><strong>{value(row,"key","name")}</strong><p>{value(row,"description")}</p><small>Stored value</small><input value={settingEdits[String(row.key??row.id)]??String(row.value??"")} onChange={e=>setSettingEdits(old=>({...old,[String(row.key??row.id)]:e.target.value}))}/></div><button className="action-secondary" disabled={busy} onClick={()=>void setSetting(String(row.key??row.id))}>Save</button></article>)}</div>
    :<div className="record-list">{rows.length===0?<Empty/>:rows.map(row=>{
      const id=String(row.id??row.public_code??row.key??Math.random());
      const status=String(row.status??row.approval_status??"").toLowerCase();
      const title=titleFor(tab,row);
      const detail=[value(row,"city"),value(row,"shop_type","vehicle_type","category"),value(row,"phone","customer_phone","email")].filter(x=>x!=="—").join(" · ");
      return <article className="record-card" key={id}><div className="record-icon">{({shops:"⌂",agents:"♧",products:"▤",orders:"▣",customers:"♙",audit:"☷",admins:"◎"} as Record<string,string>)[tab]||"•"}</div><div className="record-body"><div className="record-title-row"><strong>{title}</strong><span className={"status-pill "+(status==="approved"||status==="active"||status==="delivered"?"good":status==="pending"||status==="placed"?"pending":status==="blocked"||status==="suspended"||status==="rejected"||status==="cancelled"?"bad":"")}>{status||"record"}</span></div><p>{detail||value(row,"address","delivery_address","entity_type","detail")}</p><small>{tab==="orders"?`Total ₹${value(row,"total_amount","total") } · Payment ${value(row,"payment_status")}`:tab==="products"?`Price ₹${value(row,"price")} · Stock ${value(row,"stock_qty")}`:tab==="audit"?`Entity #${value(row,"entity_id")} · ${value(row,"created_at")}`:value(row,"created_at","updated_at","email")}</small></div><div className="record-actions">
       {(tab==="shops"||tab==="agents"||tab==="products")&&<>{status!=="approved"&&status!=="active"&&<button className="action-primary small" disabled={busy} onClick={()=>void updateStatus(tab as "shops"|"agents"|"products",row,"approved")}>{tab==="products"?"Approve listing":"Approve"}</button>}{status!=="suspended"&&status!=="blocked"&&<button className="action-secondary small" disabled={busy} onClick={()=>void updateStatus(tab as "shops"|"agents"|"products",row,tab==="products"?"blocked":"suspended")}>{tab==="products"?"Block":"Suspend"}</button>}</>}
       {tab==="customers"&&<button className="action-secondary small" disabled={busy} onClick={()=>void updateCustomer(row,status==="blocked"?"active":"blocked")}>{status==="blocked"?"Unblock":"Block"}</button>}
       {tab==="orders"&&(TRANSITIONS[status]||[]).length>0&&<select aria-label={"Next status for "+title} disabled={busy} value="" onChange={e=>{if(e.target.value)void changeOrder(row,e.target.value);}}><option value="">Change status…</option>{(TRANSITIONS[status]||[]).map(next=><option key={next} value={next}>{next.replaceAll("_"," ")}</option>)}</select>}
       {tab==="admins"&&isSuperAdmin&&<button className="action-secondary small" disabled={busy} onClick={()=>void toggleAdmin(row)}>{row.is_active?"Deactivate":"Activate"}</button>}
      </div></article>;
    })}</div>}
    <div className="main-footer">VEGZ ADMIN · {rows.length?rows.length+" records in this view":"Operational controls"} · Changes are saved through FastAPI.</div>
   </section>
  </div>
 </main>;
}
function Empty(){return <div className="empty-state"><span>✓</span><strong>No records to show</strong><p>This section is empty or has not loaded any data yet.</p></div>}
