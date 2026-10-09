"use client";
import { Children, isValidElement, type ReactNode } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import s from "./manager.module.css";

type Option = { value: string; label: ReactNode; disabled?: boolean };
function text(node: ReactNode): string {
  return Children.toArray(node).map(child=>isValidElement<{children?:ReactNode}>(child)?text(child.props.children):String(child)).join("");
}
function options(nodes: ReactNode): Option[] {
  const result: Option[]=[];
  Children.forEach(nodes,node=>{
    if(!isValidElement<{value?:string|number;children?:ReactNode;disabled?:boolean}>(node))return;
    if(node.type==="option")result.push({value:String(node.props.value??text(node.props.children)),label:node.props.children,disabled:node.props.disabled});
    else result.push(...options(node.props.children));
  });
  return result;
}
export function Dropdown({ value, onValueChange, children, className, id, disabled, required, name, ...aria }: {
  value: string | number; onValueChange: (value: string) => void; children: ReactNode; className?: string;
  id?: string; disabled?: boolean; required?: boolean; name?: string;
  "aria-label"?: string; "aria-describedby"?: string; "aria-invalid"?: boolean;
}) {
  const items=options(children),placeholder=items.find(item=>item.value==="")?.label;
  let empty="__kami_select_empty__";
  while(items.some(item=>item.value===empty))empty+="_";
  return <Select value={String(value)} onValueChange={next=>onValueChange(next===empty?"":next)} disabled={disabled} required={required} name={name}>
    <SelectTrigger id={id} className={s.dropdownTrigger+(className?" "+className:"")} {...aria}><SelectValue placeholder={placeholder??"Chọn một giá trị"}/></SelectTrigger>
    <SelectContent className={s.dropdownContent} position="popper" sideOffset={6}>{items.map(item=><SelectItem key={item.value||empty} value={item.value||empty} data-value={item.value} disabled={item.disabled} className={s.dropdownItem}>{item.label}</SelectItem>)}</SelectContent>
  </Select>;
}
