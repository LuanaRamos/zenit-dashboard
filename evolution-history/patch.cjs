const fs = require('node:fs');
const path = require('node:path');
function patchSource(source) {
  const once = (old, replacement) => {
    const first = source.indexOf(old);
    if (first < 0 || source.indexOf(old, first + old.length) >= 0)
      throw new Error('Upstream anchor missing or ambiguous: ' + old.slice(0, 110));
    source = source.slice(0, first) + replacement + source.slice(first + old.length);
  };
  once('export class BaileysStartupService extends ChannelStartupService {',
    'export class BaileysStartupService extends ChannelStartupService {\n  private readonly zenitHistory = new ZenitHistory(this);');
  source = "import { ZenitHistory } from './zenit-history';\n" + source;
  once("if (connection === 'open') {\n      this.instance.wuid",
    "if (connection === 'open') {\n      this.zenitHistory.onConnection('open');\n      this.instance.wuid");
  once("if (connection === 'close') {\n      const statusCode",
    "if (connection === 'close') {\n      this.zenitHistory.onConnection('close');\n      const statusCode");
  once("if (connection === 'connecting') {\n      this.sendDataWebhook",
    "if (connection === 'connecting') {\n      this.zenitHistory.onConnection('connecting');\n      this.sendDataWebhook");
  once("if (syncType === proto.HistorySync.HistorySyncType.ON_DEMAND) {\n          console.log('received on-demand history sync, messages=', messages);",
    "this.zenitHistory.onHistory(syncType === proto.HistorySync.HistorySyncType.ON_DEMAND);\n        if (syncType === proto.HistorySync.HistorySyncType.ON_DEMAND) {\n          console.log('received on-demand history sync, count=', messages.length);");
  // Do not leave a remotely triggerable debug command in the customized image.
  once("            if (text == 'onDemandHistSync') {\n              const messageId = await this.client.fetchMessageHistory(50, received.key, received.messageTimestamp!);\n              console.log('requested on-demand sync, id=', messageId);\n            }", "");
  // For on-demand imports, do not trust an old cached set of IDs.
  once("chatwootImport.getRepositoryMessagesCache(instance) ??\n            (",
    "(syncType === proto.HistorySync.HistorySyncType.ON_DEMAND ? null : chatwootImport.getRepositoryMessagesCache(instance)) ??\n            (");
  once("          messagesRaw.push(this.prepareMessage(m));",
    "          messagesRaw.push(this.prepareMessage(m));\n          messagesRepository.add(m.key.id);");
  return source;
}
if (require.main === module) {
  const root = process.argv[2] || '/evolution';
  const target = path.join(root, 'src/api/integrations/channel/whatsapp/whatsapp.baileys.service.ts');
  fs.writeFileSync(target, patchSource(fs.readFileSync(target, 'utf8')));
  fs.copyFileSync(path.join(__dirname, 'zenit-history.ts'), path.join(path.dirname(target), 'zenit-history.ts'));
  console.log('Zenit history patch applied.');
}
module.exports = { patchSource };
