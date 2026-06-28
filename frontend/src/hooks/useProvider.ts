import { LiteRTProvider } from '../providers/liteRTProvider'
import { OllamaProvider } from '../providers/ollamaProvider'
import type { ProviderClient, ProviderName } from '../providers/provider'

const providers: Record<ProviderName, ProviderClient> = {
  liteRT: new LiteRTProvider(),
  ollama: new OllamaProvider()
}

export function getProvider(name: ProviderName): ProviderClient {
  return providers[name]
}
