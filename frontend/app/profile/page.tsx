'use client';
import {FormEvent,useEffect,useState} from 'react';
import Link from 'next/link';
import {StudentHeader} from '@/app/components/student-header';
import {SettingsIcon,UserIcon} from '@/app/components/ui-icons';
import {useAuth} from '@/app/providers/auth-context';
import {apiClient} from '@/services/api-client';

const emptyProfile={full_name:'',username:'',email:'',bio:'',institution:'',major:'',avatar_url:''};

export default function ProfilePage(){
 const{user,loading,setUser}=useAuth();const[form,setForm]=useState<any>(emptyProfile),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('');
 const[password,setPassword]=useState({current:'',next:'',confirm:''});
 useEffect(()=>{if(user)apiClient.getCurrentUser().then(profile=>setForm({...emptyProfile,...profile})).catch(()=>setError('Profile could not be loaded.'))},[user]);
 function change(field:string,value:string){setForm((current:any)=>({...current,[field]:value}));setMessage('');setError('')}
 async function save(event:FormEvent){event.preventDefault();setBusy(true);setMessage('');setError('');try{const updated=await apiClient.updateProfile({full_name:form.full_name,username:form.username,email:form.email,bio:form.bio||null,institution:form.institution||null,major:form.major||null,avatar_url:form.avatar_url||null});setForm({...emptyProfile,...updated});setUser(updated);setMessage('Profile updated successfully.')}catch(err:any){setError(err?.response?.data?.detail||'Profile could not be updated.')}finally{setBusy(false)}}
 async function savePassword(event:FormEvent){event.preventDefault();setMessage('');setError('');if(password.next!==password.confirm){setError('New password confirmation does not match.');return}setBusy(true);try{await apiClient.changePassword(password.current,password.next);setPassword({current:'',next:'',confirm:''});setMessage('Password updated successfully.')}catch(err:any){setError(err?.response?.data?.detail||'Password could not be updated.')}finally{setBusy(false)}}
 if(loading)return <main className="app-page grid place-items-center">Loading profile...</main>;
 if(!user)return <main className="app-page grid place-items-center"><Link href="/login" className="btn-primary">Sign in</Link></main>;
 const initials=(form.full_name||user.full_name||'U').split(' ').slice(0,2).map((part:string)=>part[0]).join('').toUpperCase();
 return <main className="app-page min-h-screen pb-28 md:pl-[244px] md:pb-12"><StudentHeader/><div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-11">
  <div className="flex items-start justify-between gap-5"><div><p className="eyebrow">Account settings</p><h1 className="page-title">Your profile</h1><p className="page-description">Manage how your identity appears across ElectroQuest.</p></div><SettingsIcon className="mt-2 hidden h-7 w-7 text-slate-400 sm:block"/></div>
  {(message||error)&&<div className={`mt-6 rounded-xl border px-4 py-3 text-sm font-semibold ${error?'border-red-200 bg-red-50 text-red-700':'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>{error||message}</div>}
  <div className="mt-8 grid items-start gap-6 lg:grid-cols-[280px_1fr]"><aside className="rounded-2xl border border-slate-200 bg-white p-6 text-center dark:border-slate-800 dark:bg-slate-900"><div className="mx-auto grid h-24 w-24 place-items-center overflow-hidden rounded-2xl bg-[#101b2d] text-2xl font-black text-white">{form.avatar_url?<img src={form.avatar_url} alt="Profile avatar" className="h-full w-full object-cover"/>:initials}</div><h2 className="mt-5 truncate text-xl font-black">{form.full_name||user.full_name}</h2><p className="mt-1 truncate text-sm text-slate-500">@{form.username||user.username}</p><div className="mt-5 border-t border-slate-100 pt-5 text-left dark:border-slate-800"><p className="text-[10px] font-black uppercase tracking-wider text-slate-400">Member since</p><p className="mt-1 text-sm font-semibold">{form.created_at?new Date(form.created_at).toLocaleDateString(undefined,{month:'long',year:'numeric'}):'ElectroQuest learner'}</p></div></aside>
   <div className="space-y-6"><form onSubmit={save} className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900 sm:p-8"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-lg bg-blue-50 text-blue-600"><UserIcon/></span><div><h2 className="text-lg font-black">Profile information</h2><p className="text-sm text-slate-500">Your public identity and learning details.</p></div></div><div className="mt-7 grid gap-5 sm:grid-cols-2">
    <Field label="Full name" value={form.full_name} onChange={(v)=>change('full_name',v)} required/>
    <Field label="Username" value={form.username} onChange={(v)=>change('username',v)} required prefix="@"/>
    <Field label="Email" type="email" value={form.email} onChange={(v)=>change('email',v)} required/>
    <Field label="Avatar URL" value={form.avatar_url||''} onChange={(v)=>change('avatar_url',v)} placeholder="https://..."/>
    <Field label="Organization (optional)" value={form.institution||''} onChange={(v)=>change('institution',v)}/>
    <Field label="Focus area (optional)" value={form.major||''} onChange={(v)=>change('major',v)} placeholder="Power systems, embedded, control..."/>
    <label className="sm:col-span-2"><span className="mb-2 block text-sm font-bold">Short bio</span><textarea className="input-base min-h-28 resize-y" maxLength={500} value={form.bio||''} onChange={e=>change('bio',e.target.value)} placeholder="Tell other learners what you are building or studying."/></label>
   </div><div className="mt-7 flex justify-end"><button disabled={busy} className="btn-primary min-w-36">{busy?'Saving...':'Save changes'}</button></div></form>
   <form onSubmit={savePassword} className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900 sm:p-8"><h2 className="text-lg font-black">Password</h2><p className="mt-1 text-sm text-slate-500">Use at least eight characters for your new password.</p><div className="mt-6 grid gap-5 sm:grid-cols-3"><Field label="Current password" type="password" value={password.current} onChange={v=>setPassword({...password,current:v})} required/><Field label="New password" type="password" value={password.next} onChange={v=>setPassword({...password,next:v})} required minLength={8}/><Field label="Confirm password" type="password" value={password.confirm} onChange={v=>setPassword({...password,confirm:v})} required minLength={8}/></div><div className="mt-7 flex justify-end"><button disabled={busy} className="btn-secondary">Update password</button></div></form></div>
  </div>
 </div></main>
}

function Field({label,value,onChange,type='text',required=false,placeholder='',prefix,minLength}:{label:string,value:string,onChange:(value:string)=>void,type?:string,required?:boolean,placeholder?:string,prefix?:string,minLength?:number}){return <label><span className="mb-2 block text-sm font-bold">{label}</span><div className="relative">{prefix&&<span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">{prefix}</span>}<input className={`input-base ${prefix?'pl-8':''}`} type={type} value={value} onChange={e=>onChange(e.target.value)} required={required} placeholder={placeholder} minLength={minLength}/></div></label>}
