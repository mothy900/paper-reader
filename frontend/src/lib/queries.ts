import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'

export const usePapers = () => useQuery({ queryKey: ['papers'], queryFn: api.listPapers })

export const useBlocks = (paperId: string | null) =>
  useQuery({
    queryKey: ['blocks', paperId],
    queryFn: () => api.getBlocks(paperId!),
    enabled: paperId !== null,
    staleTime: Infinity,
  })

export const useUploadPaper = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.uploadPaper,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['papers'] }),
  })
}
