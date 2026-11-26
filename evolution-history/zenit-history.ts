/**
 * Zenit: opt-in, bounded, automatic WhatsApp history requests.
 * Derived from the Evolution API 2.3.7 on-demand synchronization mechanism.
 * The worker never sends a chat message or changes read receipts.
 */
type Anchor = { jid: string; key: any; ts: number };
type Checkpoint = { jid: string; nextAt: Date };
const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));
const clamp = (name: string, fallback: number, min: number, max: number) => {
  const raw = process.env[name];
  const n = raw && /^\d+$/.test(raw) ? Number(raw) : fallback;
  return Math.min(max, Math.max(min, n));
};
const list = (name: string) => (process.env[name] || '').split(',').map(s => s.trim()).filter(Boolean);
const individual = (jid: string) => /^[^@]+@(s\.whatsapp\.net|lid)$/.test(jid);

export class ZenitHistory {
  private timer: ReturnType<typeof setTimeout> | undefined;
  private running = false;
  private epoch = 0;
  private lastInitialBatch = 0;
  constructor(private readonly service: any) {}

  private get db() { return this.service.prismaRepository; }
  private get name(): string { return this.service.instance.name; }
  private get id(): string { return this.service.instanceId; }

  private enabled() {
    return process.env.ZENIT_HISTORY_ENABLED === 'true'
      && list('ZENIT_HISTORY_INSTANCES').includes(this.name)
      && process.env.DATABASE_PROVIDER === 'postgresql'
      && process.env.DATABASE_SAVE_DATA_HISTORIC === 'true';
  }

  private active(epoch: number) {
    return this.enabled() && epoch === this.epoch && !this.service.endSession
      && this.service.stateConnection?.state === 'open'
      && typeof this.service.client?.fetchMessageHistory === 'function';
  }

  onConnection(state: string | undefined) {
    if (!state) return;
    this.epoch++;
    if (this.timer) clearTimeout(this.timer);
    this.timer = undefined;
    if (state === 'open' && this.enabled()) this.schedule(this.quietMs());
  }

  onHistory(onDemand: boolean) {
    if (!onDemand && this.enabled()) {
      this.lastInitialBatch = Date.now();
      if (!this.running && this.service.stateConnection?.state === 'open') {
        this.schedule(this.quietMs());
      }
    }
  }

  private quietMs() { return clamp('ZENIT_HISTORY_QUIET_SECONDS', 120, 30, 900) * 1000; }
  private intervalMs() { return clamp('ZENIT_HISTORY_INTERVAL_SECONDS', 300, 60, 3600) * 1000; }
  private schedule(ms: number) {
    if (!this.enabled() || this.service.stateConnection?.state !== 'open') return;
    if (this.timer) clearTimeout(this.timer);
    const epoch = this.epoch;
    this.timer = setTimeout(() => {
      this.timer = undefined;
      void this.run(epoch);
    }, ms);
  }

  private async ensureTable() {
    await this.db.$executeRaw`
      CREATE TABLE IF NOT EXISTS "ZenitHistoryCheckpoint" (
        "instanceId" text NOT NULL,
        "jid" text NOT NULL,
        "lastTimestamp" integer NOT NULL,
        "nextAt" timestamp with time zone NOT NULL,
        "updatedAt" timestamp with time zone NOT NULL DEFAULT now(),
        PRIMARY KEY ("instanceId", "jid")
      )
    `;
  }

  private async candidates(limit: number): Promise<Anchor[]> {
    const target = list('ZENIT_HISTORY_JIDS').filter(individual);
    // A configured but malformed allow-list must never expand the scope.
    if (process.env.ZENIT_HISTORY_JIDS?.trim() && !target.length) return [];
    const restrict = target.length > 0;
    // Parameterized PostgreSQL query. No private message text is selected.
    return this.db.$queryRaw`
      WITH anchors AS (
        SELECT DISTINCT ON (m."key"->>'remoteJid')
          m."key"->>'remoteJid' AS jid, m."key" AS key, m."messageTimestamp" AS ts
        FROM "Message" m
        WHERE m."instanceId" = ${this.id}
          AND (m."key"->>'remoteJid') ~ '^[^@]+@(s[.]whatsapp[.]net|lid)$'
          AND COALESCE(m."key"->>'id', '') <> ''
          AND m."messageTimestamp" > 0
          AND (NOT ${restrict} OR (m."key"->>'remoteJid') = ANY(string_to_array(${target.join(',')}, ',')))
        ORDER BY m."key"->>'remoteJid', m."messageTimestamp" ASC, m.id ASC
      )
      SELECT a.jid, a.key, a.ts FROM anchors a
      LEFT JOIN "ZenitHistoryCheckpoint" c
        ON c."instanceId" = ${this.id} AND c."jid" = a.jid
      WHERE c."nextAt" IS NULL OR c."nextAt" <= now() OR a.ts < c."lastTimestamp"
      ORDER BY c."updatedAt" ASC NULLS FIRST, a.ts ASC, a.jid ASC
      LIMIT ${limit}
    `;
  }

  private async oldest(jid: string): Promise<Anchor | undefined> {
    const rows: Anchor[] = await this.db.$queryRaw`
      SELECT "key"->>'remoteJid' AS jid, "key" AS key, "messageTimestamp" AS ts
      FROM "Message"
      WHERE "instanceId" = ${this.id}
        AND "key"->>'remoteJid' = ${jid}
        AND COALESCE("key"->>'id', '') <> ''
        AND "messageTimestamp" > 0
      ORDER BY "messageTimestamp" ASC, id ASC LIMIT 1
    `;
    return rows[0];
  }

  private async checkpoint(anchor: Anchor, minutes: number) {
    const next = new Date(Date.now() + minutes * 60000);
    await this.db.$executeRaw`
      INSERT INTO "ZenitHistoryCheckpoint" ("instanceId", "jid", "lastTimestamp", "nextAt")
      VALUES (${this.id}, ${anchor.jid}, ${anchor.ts}, ${next})
      ON CONFLICT ("instanceId", "jid") DO UPDATE SET
        "lastTimestamp" = EXCLUDED."lastTimestamp",
        "nextAt" = EXCLUDED."nextAt", "updatedAt" = now()
    `;
  }

  private async run(epoch: number) {
    if (!this.active(epoch)) return;
    if (this.running) { this.schedule(this.quietMs()); return; }
    const remainingQuiet = this.quietMs() - (Date.now() - this.lastInitialBatch);
    if (remainingQuiet > 0) { this.schedule(remainingQuiet); return; }
    this.running = true;
    let requests = 0, advanced = 0, stopped = 0;
    try {
      await this.ensureTable();
      const candidates = await this.candidates(clamp('ZENIT_HISTORY_MAX_CHATS', 5, 1, 20));
      const batches = clamp('ZENIT_HISTORY_MAX_BATCHES', 2, 1, 5);
      const waitMs = clamp('ZENIT_HISTORY_WAIT_SECONDS', 45, 15, 120) * 1000;
      for (let anchor of candidates) {
        if (!this.active(epoch)) break;
        if (Date.now() - this.lastInitialBatch < this.quietMs()) break;
        if (!individual(anchor.jid) || !anchor.key?.id || !Number.isInteger(anchor.ts)) continue;
        let progressed = false;
        for (let i = 0; i < batches && this.active(epoch); i++) {
          if (Date.now() - this.lastInitialBatch < this.quietMs()) break;
          requests++;
          try {
            await this.service.client.fetchMessageHistory(50, anchor.key, anchor.ts);
          } catch {
            if (this.active(epoch)) await this.checkpoint(anchor, 15);
            stopped++;
            break;
          }
          const deadline = Date.now() + waitMs;
          let next: Anchor | undefined;
          while (Date.now() < deadline && this.active(epoch)) {
            await sleep(5000);
            if (!this.active(epoch)) break;
            const candidate = await this.oldest(anchor.jid);
            if (candidate && candidate.ts < anchor.ts) { next = candidate; break; }
          }
          if (!this.active(epoch)) break;
          if (!next) {
            await this.checkpoint(anchor, clamp('ZENIT_HISTORY_NO_PROGRESS_MINUTES', 1440, 60, 10080));
            stopped++;
            break;
          }
          anchor = next;
          progressed = true;
          advanced++;
          // Durable checkpoint; after a restart the oldest persisted message is the cursor.
          await this.checkpoint(anchor, 5);
          await sleep(5000);
        }
        // No phone numbers, message content, keys, or ad click identifiers in worker logs.
        if (progressed) console.log('[zenit-history] chat advanced');
      }
      console.log('[zenit-history] round', { requests, advanced, stopped });
    } catch {
      // Fail closed, without dumping credentials or message contents.
      console.warn('[zenit-history] round failed; retry scheduled');
    } finally {
      this.running = false;
      if (this.active(epoch)) this.schedule(this.intervalMs());
      else if (this.enabled() && this.service.stateConnection?.state === 'open') this.schedule(this.quietMs());
    }
  }
}
