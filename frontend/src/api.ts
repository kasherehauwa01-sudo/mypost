const root=`${(import.meta.env.BASE_URL||'/').replace(/\/$/,'')}/api`;
type ApiError = {detail?:string|Array<{msg:string}>};
export async function api<T>(path:string,init?:RequestInit):Promise<T>{const r=await fetch(root+path,{...init,headers:{'Content-Type':'application/json',...init?.headers}});if(!r.ok){const body:ApiError=await r.json().catch(()=>({detail:r.statusText}));const message=Array.isArray(body.detail)?body.detail.map(item=>item.msg).join('; '):body.detail;throw new Error(message||`Ошибка HTTP ${r.status}`)}return r.status===204?undefined as T:r.json()}
export const downloadUrl=(id:number)=>`${root}/attachments/${id}/download`;
