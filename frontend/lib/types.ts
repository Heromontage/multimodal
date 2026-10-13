export type Target = 'CAD' | 'LAD' | 'LCX' | 'RCA';
export type Values = Record<string, number | string | null>;
export type Field = {name:string; label:string; group:string; kind:'number'|'category'; options:(string|number)[]|null; default:string|number; unit:string; min:number|null; max:number|null; constant:boolean; used_by:Target[]};
export type TargetInfo = {model:string; auc:number; threshold:number; calibrated:boolean; selected_features:string[]};
export type Schema = {fields:Field[]; groups:string[]; targets:Record<Target,TargetInfo>; patient_count:number; validation:string; selection_note:string};
export type Evidence = {name:string; label:string; value:string|number|null; used:boolean; contribution:number};
export type Prediction = TargetInfo & {probability:number; positive:boolean; features:Evidence[]; prior_log_odds:number};
export type Results = {predictions:Record<Target,Prediction>; warnings:string[]; explanation:string};
export const targetNames:Record<Target,string> = {CAD:'Overall coronary disease', LAD:'Left anterior descending', LCX:'Left circumflex', RCA:'Right coronary artery'};

export type AccountSession = {user: {email: string}; inputs: Values | null};
