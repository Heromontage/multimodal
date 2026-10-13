'use client';
import {useState} from 'react';
import {ActivityIcon as Activity, ArrowCounterClockwise, ArrowRight, CaretDown, CircleNotch, Flask, MagnifyingGlass, SlidersHorizontal} from '@phosphor-icons/react';
import {Field, Schema, Values} from '@/lib/types';
export function optionLabel(v:string|number){return v==='Fmale'?'Female':v==='Y'?'Yes':v==='N'?'No':String(v);}
export default function InputPanel({schema,values,reference,busy,dirty,saved,errors,onChange,onReset,onAssess}:{schema:Schema;values:Values;reference:boolean;busy:boolean;dirty:boolean;saved:boolean;errors:Record<string,string>;onChange:(key:string,value:string|number|null)=>void;onReset:()=>void;onAssess:()=>void}){
  const [group,setGroup]=useState('Profile');const [query,setQuery]=useState('');
  const fields=schema.fields.filter(f=>query?`${f.name} ${f.label}`.toLowerCase().includes(query.toLowerCase()):f.group===group);
  const count=Object.values(values).filter(v=>v!==null).length;
  return <section className="input-panel panel" aria-labelledby="input-heading">
    <div className="panel-heading"><span className="heading-icon"><SlidersHorizontal size={20}/></span><div><h2 id="input-heading">Patient inputs</h2><p>Clinical findings & measurements</p></div><span className="count-tag">{count}/55</span></div>
    <div className="reference-note"><Flask size={16}/><span>{reference?'Reference values loaded. Replace with patient findings.':dirty?'Unsaved edits. Run an assessment to save them.':'Your saved inputs are loaded.'}</span></div>
    <div className="input-search"><MagnifyingGlass size={17}/><input aria-label="Search all 55 inputs" placeholder="Find a measurement…" value={query} onChange={e=>setQuery(e.target.value)}/></div>
    <div className="group-tabs" role="tablist" aria-label="Input sections">{schema.groups.map(g=><button key={g} role="tab" aria-selected={group===g&&!query} className={group===g&&!query?'active':''} onClick={()=>{setGroup(g);setQuery('');}}>{g}</button>)}</div>
    <div className="input-fields"><div className="section-label"><h3>{query?'Search results':group}</h3><span>{fields.length} parameters</span></div><div className="field-grid">{fields.map(f=><FieldInput key={f.name} field={f} value={values[f.name]} error={errors[f.name]} onChange={v=>onChange(f.name,v)}/>)}</div>{!fields.length&&<p>No inputs match this search.</p>}</div>
    <div className="input-footer"><div><span className="small-dot"/>All 55 dataset inputs available<button onClick={onReset} disabled={busy}><ArrowCounterClockwise size={13}/>Reset</button></div><button className="button primary run-button" onClick={onAssess} disabled={busy}>{busy?<CircleNotch size={19} className="spin"/>:<Activity size={19}/>} {busy?'Calculating…':'Run assessment'}<ArrowRight size={17}/></button><p>{busy?'Running assessment…':dirty?'Changes will be saved when you run an assessment.':saved?'These inputs are saved to your account.':'Run an assessment to save these inputs to your account.'}</p></div>
  </section>;
}
function FieldInput({field:f,value,error,onChange}:{field:Field;value:string|number|null;error?:string;onChange:(v:string|number|null)=>void}){
  const id=`field-${f.name.replace(/[^a-zA-Z0-9]/g,'-')}`;
  const binary=f.options?.length===2&&f.options.every(v=>['N','Y',0,1].includes(v));
  return <div className={`field ${error?'field-error':''}`}><label htmlFor={id}>{f.label}<span title={`Dataset column: ${f.name}. Used by: ${f.used_by.join(', ')||'none'}.`}>{f.constant?'Constant':f.unit}</span></label>
    {f.kind==='number'?<input id={id} type="number" min="0" max="1000000" step="any" value={value??''} onChange={e=>onChange(e.target.value===''?null:Number(e.target.value))} aria-invalid={!!error} aria-describedby={`${id}-hint`}/>:<div className="select-wrap"><select id={id} value={value===null?'__missing':String(value)} disabled={f.constant} aria-invalid={!!error} onChange={e=>onChange(e.target.value==='__missing'?null:f.options?.find(v=>String(v)===e.target.value)??null)}>{f.options?.map(v=><option key={String(v)} value={String(v)}>{binary?(v===1||v==='Y'?'Yes':'No'):optionLabel(v)}</option>)}<option value="__missing">Unknown / missing</option></select><CaretDown size={13}/></div>}
    <span className="field-hint" id={`${id}-hint`}>{error||(f.constant?'No variation in training data':f.kind==='number'?`Training range ${f.min}–${f.max}`:f.name!==f.label?f.name:'Dataset category')}</span></div>;
}
