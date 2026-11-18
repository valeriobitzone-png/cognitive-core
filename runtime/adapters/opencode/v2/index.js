import { WorldCoreV2Plugin } from '../worldcore-v2.js';
// Plugin.define in the official SDK is an identity function; this is its runtime definition.
export default { id: 'worldcore', setup: WorldCoreV2Plugin };
