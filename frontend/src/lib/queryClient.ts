import { QueryClient } from '@tanstack/react-query'

/** React 밖(스토어)에서도 캐시를 무효화할 수 있게 모듈로 둔다. */
export const queryClient = new QueryClient()
