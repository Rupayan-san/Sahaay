import apiClient from './client';
import type { VerificationResponse } from '../types';

export async function verifyImages(
  assignmentId: string,
  imagePaths: string[],
): Promise<VerificationResponse> {
  const response = await apiClient.post<VerificationResponse>(
    `/api/assignments/${assignmentId}/verify-images`,
    { image_paths: imagePaths },
  );
  return response.data;
}
