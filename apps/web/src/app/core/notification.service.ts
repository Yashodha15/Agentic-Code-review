import { Injectable, signal } from '@angular/core';

export type NotificationTone = 'info' | 'success' | 'danger';
export interface AppNotification { id:number; tone:NotificationTone; title:string; message:string; }

@Injectable({providedIn:'root'})
export class NotificationService {
  readonly items=signal<AppNotification[]>([]); readonly history=signal<AppNotification[]>([]); readonly panelOpen=signal(false); private nextId=1;
  show(tone:NotificationTone,title:string,message:string):void{const item={id:this.nextId++,tone,title,message};this.items.update(items=>[item,...items].slice(0,4));this.history.update(items=>[item,...items].slice(0,20));setTimeout(()=>this.dismiss(item.id),6500)}
  dismiss(id:number):void{this.items.update(items=>items.filter(item=>item.id!==id))}
  togglePanel():void{this.panelOpen.update(open=>!open)}
}
