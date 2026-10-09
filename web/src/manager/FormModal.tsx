"use client";
import { useRef, type ReactNode } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import s from "./manager.module.css";

export function FormModal({ title, description, busy = false, onClose, children, compact = false }: {
  title: string; description: string; busy?: boolean; onClose: () => void; children: ReactNode; compact?: boolean;
}) {
  const trigger = useRef<HTMLElement | null>(null);
  return <Dialog open onOpenChange={open=>{if(!open&&!busy)onClose();}}>
    <DialogContent className={s.formModal+(compact?" "+s.compactModal:"")} showCloseButton={!busy}
      onOpenAutoFocus={()=>{trigger.current=document.activeElement as HTMLElement;}}
      onCloseAutoFocus={e=>{e.preventDefault();if(trigger.current?.isConnected)trigger.current.focus();}}
      onPointerDownOutside={e=>e.preventDefault()}
      onEscapeKeyDown={e=>{if(busy)e.preventDefault();}}>
      <DialogHeader className={s.modalHeader}><DialogTitle>{title}</DialogTitle><DialogDescription>{description}</DialogDescription></DialogHeader>
      <div className={s.modalBody}>{children}</div>
    </DialogContent>
  </Dialog>;
}
