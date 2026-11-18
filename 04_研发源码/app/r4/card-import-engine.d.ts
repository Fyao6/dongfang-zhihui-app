declare const engine: {version:string;parseStrict(text:string):any;canonical(value:any):string;inspect(payload:any,baseData:any|null):{payload:any;summary:any;issues:any[];diff:any[]};packWire(value:any):{codec:string;dictionary:string[];result:any};decodeWire(wire:any):any};
export default engine;
