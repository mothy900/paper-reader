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

export const useImportPaper = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.importPaper,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['papers'] }),
  })
}

export const useUsage = (paperId: string | null) =>
  useQuery({ queryKey: ['usage', paperId], queryFn: () => api.getUsage(paperId!), enabled: paperId !== null })

export const useHistory = (paperId: string | null) =>
  useQuery({ queryKey: ['history', paperId], queryFn: () => api.getHistory(paperId!), enabled: paperId !== null })

export const useProfile = () => useQuery({ queryKey: ['profile'], queryFn: api.getProfile, staleTime: Infinity })

export const useSaveProfile = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.putProfile,
    onSuccess: (profile) => qc.setQueryData(['profile'], profile),
  })
}

/** 저장된 준비 카드 (LLM 호출 없음) */
export const useStoredPrep = (paperId: string | null) =>
  useQuery({ queryKey: ['prep', paperId], queryFn: () => api.getPrep(paperId!), enabled: paperId !== null })
