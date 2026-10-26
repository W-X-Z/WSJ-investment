import {chromium} from "playwright";
import {mkdirSync} from "node:fs";
const output="../../research/preview";
mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true});
let hadError=false;
async function check(viewport,label){
 const page=await browser.newPage({viewport,deviceScaleFactor:1});
 const errors=[];page.on("pageerror",e=>errors.push(e.message));
 await page.goto("http://localhost:3011/map",{waitUntil:"networkidle"});
 await page.locator(".sc-graph-node").first().waitFor({state:"visible"});
 await page.waitForTimeout(850);
 let before=await page.locator(".sc-world").getAttribute("style");
 const fit=page.locator(".sc-icon-button");
 await fit.click();await page.waitForTimeout(200);
 let after=await page.locator(".sc-world").getAttribute("style");
 const nodes=await page.locator(".sc-graph-node").count();
 const links=await page.locator(".sc-link-path").count();
 const viewportBox=await page.locator(".sc-viewport").boundingBox();
 const nodeBox=await page.locator(".sc-graph-node").first().boundingBox();
 const allVisible=await page.locator(".sc-graph-node").evaluateAll(els=>els.filter(el=>{
  const r=el.getBoundingClientRect(),v=document.querySelector(".sc-viewport")?.getBoundingClientRect();
  return v&&r.right>v.left&&r.left<v.right&&r.bottom>v.top&&r.top<v.bottom;
 }).length);
 await page.locator(".sc-shell").screenshot({path:`${output}/industry-canvas-${label}.png`,animations:"disabled"});
 await page.getByRole("button",{name:"HBM",exact:true}).click();
 await page.waitForTimeout(200);
 const scopedCount=await page.locator(".sc-graph-node").count();
 await page.locator(".sc-shell").screenshot({path:`${output}/industry-canvas-${label}-hbm.png`,animations:"disabled"});
 const chosen=page.locator(".sc-graph-node").filter({hasText:"Camtek"}).first();
 if(await chosen.count()){await chosen.click();await page.waitForTimeout(100);}
 const inspector=await page.locator(".sc-inspector").innerText().catch(()=>"");
 console.log(JSON.stringify({label,before,after,nodes,links,scopedCount,viewportBox,nodeBox,visibleNodes:allVisible,inspector:inspector.slice(0,150),pageErrors:errors}));
 if(errors.length||nodes<80||scopedCount<15)hadError=true;
 await page.close();
}
await check({width:1600,height:1080},"desktop");
await check({width:390,height:844},"mobile");
await browser.close();
if(hadError)process.exit(1);
