/** Incomplete exchange integration: fail closed. No network or wallet actions. */
export class SwapExecutionUnavailable extends Error {
  constructor() { super('Live swap execution is not configured.'); this.name = 'SwapExecutionUnavailable'; }
}
export async function executeSwap(
  _inputMint: string,
  _outputMint: string,
  _amount: number,
  _slippagePercent: number,
  _env: { SOLANA_RPC_URL?: string; PRIVATE_KEY?: string }
): Promise<string> {
  throw new SwapExecutionUnavailable();
}
