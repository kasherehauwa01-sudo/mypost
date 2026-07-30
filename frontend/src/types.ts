export type Attachment={id:number;filename:string;content_type:string;size:number;sender?:string;date?:string;folder?:string};
export type Message={id:number;account_id:number;folder:string;subject:string;sender:string;recipients:string;cc:string;bcc:string;sent_at?:string;size:number;html_body:string;text_body:string;is_read:boolean;is_important:boolean;attachments:Attachment[]};
export type Account={id:number;name:string;email:string;username:string;imap_host:string;imap_port:number;imap_ssl:boolean;smtp_host:string;smtp_port:number;smtp_ssl:boolean;smtp_username:string;enabled:boolean};
