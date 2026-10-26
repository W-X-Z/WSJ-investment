/** Shared curated bilingual aliases: research ontology owns the canonical JSON.
 * Lexical links are research leads, not verified measurement or supply contracts.
 */
import dictionary from "@/data/node-aliases.json";
export const TECHNICAL_ALIASES = dictionary.aliases as Record<string,string[]>;
export function relevantHistoricalTerms(node:{id:string;label:string}):string[]{
 const curated=TECHNICAL_ALIASES[node.id]??[];
 return Array.from(new Set(curated)).map(x=>x.toLowerCase()).filter(x=>x.length>=4);
}
