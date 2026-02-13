import axios from 'axios';

const api = axios.create({
  headers: {
    'Content-Type': 'application/json',
  },
});

// Auth
export const getAuthStatus = () => api.get('/auth/status');
export const getSettings = () => api.get('/auth/settings');
export const saveSettings = (data) => api.post('/auth/settings', data);
export const disconnectGmail = () => api.post('/auth/gmail/disconnect');
export const getGmailConnectUrl = () => '/auth/gmail/connect';

// Templates
export const getTemplates = () => api.get('/api/templates');
export const getTemplate = (id) => api.get(`/api/templates/${id}`);
export const createTemplate = (data) => api.post('/api/templates', data);
export const updateTemplate = (id, data) => api.put(`/api/templates/${id}`, data);
export const deleteTemplate = (id) => api.delete(`/api/templates/${id}`);
export const previewTemplate = (id, sampleData) =>
  api.post(`/api/templates/${id}/preview`, { sample_data: sampleData });

// Campaigns
export const getCampaigns = () => api.get('/api/campaigns');
export const getCampaign = (id) => api.get(`/api/campaigns/${id}`);
export const createCampaign = (data) => api.post('/api/campaigns', data);
export const updateCampaign = (id, data) => api.put(`/api/campaigns/${id}`, data);
export const deleteCampaign = (id) => api.delete(`/api/campaigns/${id}`);

// Campaign Recipients
export const uploadRecipients = (id, file, mapping) => {
  const formData = new FormData();
  formData.append('file', file);
  if (mapping) {
    formData.append('mapping', JSON.stringify(mapping));
  }
  return api.post(`/api/campaigns/${id}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const getRecipients = (id) => api.get(`/api/campaigns/${id}/recipients`);
export const generatePreview = (id) => api.post(`/api/campaigns/${id}/generate-preview`);
export const approveRecipients = (id, recipientIds) =>
  api.post(`/api/campaigns/${id}/approve`, { recipient_ids: recipientIds });

// Campaign Actions
export const startCampaign = (id) => api.post(`/api/campaigns/${id}/start`);
export const pauseCampaign = (id) => api.post(`/api/campaigns/${id}/pause`);
export const resumeCampaign = (id) => api.post(`/api/campaigns/${id}/resume`);
export const cancelCampaign = (id) => api.post(`/api/campaigns/${id}/cancel`);
export const exportCampaign = (id) => `/api/campaigns/${id}/export`;

// SSE Progress
export const getCampaignProgressUrl = (id) => `/api/campaigns/${id}/progress`;

export default api;
