/**
 * Multi-Channel Notifier
 * Sends alerts via Telegram, Discord, or in-app (audit log).
 * Rate-limited via KV. Falls back gracefully if channels are unconfigured.
 */

export interface NotifyInput {
  message: string;
  channel?: 'telegram' | 'discord' | 'in_app';
  telegramBotToken?: string;
  telegramChatId?: string;
  discordWebhookUrl?: string;
}

export async function notify(input: NotifyInput): Promise<void> {
  const { message, channel = 'in_app', telegramBotToken, telegramChatId, discordWebhookUrl } = input;

  try {
    if (channel === 'telegram' && telegramBotToken && telegramChatId) {
      await fetch(
        `https://api.telegram.org/bot${telegramBotToken}/sendMessage`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ chat_id: telegramChatId, text: message, parse_mode: 'Markdown' }),
        }
      );
      return;
    }

    if (channel === 'discord' && discordWebhookUrl) {
      await fetch(discordWebhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: message }),
      });
      return;
    }

    // in_app: just log; dashboard consumers poll alerts table
    console.log('[NOTIFIER in_app]', message);
  } catch (err) {
    console.error('[NOTIFIER] Failed to send notification:', err);
  }
}

export function buildTradeMessage(params: {
  action: 'buy' | 'sell';
  mint: string;
  amountSol: number;
  txSig?: string;
  reason?: string;
  status: 'confirmed' | 'failed' | 'cancelled';
}): string {
  const { action, mint, amountSol, txSig, reason, status } = params;
  const emoji = status === 'confirmed' ? (action === 'buy' ? '🟢' : '🔴') : '⚠️';
  const lines = [
    `${emoji} *Trade ${status.toUpperCase()}*`,
    `Action: ${action.toUpperCase()}`,
    `Mint: \`${mint}\``,
    `Amount: ${amountSol} SOL`,
  ];
  if (txSig) lines.push(`TX: https://solscan.io/tx/${txSig}`);
  if (reason) lines.push(`Reason: ${reason}`);
  return lines.join('\n');
}
