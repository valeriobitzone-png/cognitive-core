/* OpenCode V2 plugin (ctx.tool.hook API). Requires worldcore.js alongside it.
 * Copy both files to the V2 project plugin directory; do NOT enable V1 plugin.
 */
import { observeWorldCoreTool, shutdownOpenCodeBridge } from './worldcore.js';
export const WorldCoreV2Plugin=async ctx=>{
  if(!ctx?.tool?.hook)throw new Error('OpenCode V2 tool.hook API is required');
  await ctx.tool.hook('execute.after',async event=>{
    const name=typeof event?.tool==='string'?event.tool:event?.tool?.name;
    const failed=event?.result?.isError===true||event?.result?.metadata?.error===true||event?.result?.metadata?.metadata?.error===true;
    await observeWorldCoreTool(name,event?.status==='completed'&&!failed,'opencode-v2');
  });
  return shutdownOpenCodeBridge;
};
