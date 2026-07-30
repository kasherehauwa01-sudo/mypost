const root=`${(import.meta.env.BASE_URL||'/').replace(/\/$/,'')}/api`;
export async function api<T>(path:string,init?:RequestInit):Promise<T>{const r=await fetch(root+path,{...init,headers:{'Content-Type':'application/json',...init?.headers}});if(!r.ok)throw new Error((await r.json().catch(()=>({detail:r.statusText}))).detail);return r.status===204?undefined as T:r.json()}
export const downloadUrl=(id:number)=>`${root}/attachments/${id}/download`;
