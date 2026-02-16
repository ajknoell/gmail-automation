import axios from 'axios';

const api = axios.create({
  headers: {
    'Content-Type': 'application/json',
  },
});

// --- Workspace helpers ---

export const getActiveWorkspaceId = () => localStorage.getItem('activeWorkspaceId');

export const setActiveWorkspaceId = (id) => {
  localStorage.setItem('activeWorkspaceId', id);
  window.dispatchEvent(new CustomEvent('workspace-changed', { detail: { workspaceId: id } }));
};

// Attach X-Workspace-Id header to every request
api.interceptors.request.use((config) => {
  const wsId = getActiveWorkspaceId();
  if (wsId) {
    config.headers['X-Workspace-Id'] = wsId;
  }
  return config;
});

// Auth
export const getAuthStatus = () => api.get('/auth/status');
export const getSettings = () => api.get('/auth/settings');
export const saveSettings = (data) => api.post('/auth/settings', data);
export const disconnectGmail = () => api.post('/auth/gmail/disconnect');
export const getGmailConnectUrl = () => '/auth/gmail/connect';

// Gmail Accounts
export const getGmailAccounts = () => api.get('/auth/gmail/accounts');
export const disconnectGmailAccount = (id) => api.delete(`/auth/gmail/accounts/${id}`);
export const setDefaultGmailAccount = (id) => api.post(`/auth/gmail/accounts/${id}/default`);

// Templates
export const getTemplates = () => api.get('/api/templates');
export const getTemplate = (id) => api.get(`/api/templates/${id}`);
export const createTemplate = (data) => api.post('/api/templates', data);
export const updateTemplate = (id, data) => api.put(`/api/templates/${id}`, data);
export const deleteTemplate = (id) => api.delete(`/api/templates/${id}`);
export const previewTemplate = (id, sampleData) =>
  api.post(`/api/templates/${id}/preview`, { sample_data: sampleData });
export const generateTemplate = (data) => api.post('/api/templates/generate', data);
export const refineTemplate = (data) => api.post('/api/templates/refine', data);

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
export const clearRecipients = (id) => api.delete(`/api/campaigns/${id}/recipients`);
export const deleteRecipient = (campaignId, recipientId) => api.delete(`/api/campaigns/${campaignId}/recipients/${recipientId}`);
export const generatePreview = (id, batchSize) =>
  api.post(`/api/campaigns/${id}/generate-preview`, batchSize != null ? { batch_size: batchSize } : {});
export const approveRecipients = (id, recipientIds) =>
  api.post(`/api/campaigns/${id}/approve`, { recipient_ids: recipientIds });
export const sendIndividual = (campaignId, recipientId) =>
  api.post(`/api/campaigns/${campaignId}/send-individual`, { recipient_id: recipientId });
export const updateRecipient = (campaignId, recipientId, data) =>
  api.put(`/api/campaigns/${campaignId}/recipients/${recipientId}`, data);
export const regenerateRecipientPreview = (campaignId, recipientId) =>
  api.post(`/api/campaigns/${campaignId}/recipients/${recipientId}/regenerate`);

// Campaign Actions
export const startCampaign = (id) => api.post(`/api/campaigns/${id}/start`);
export const pauseCampaign = (id) => api.post(`/api/campaigns/${id}/pause`);
export const resumeCampaign = (id) => api.post(`/api/campaigns/${id}/resume`);
export const cancelCampaign = (id) => api.post(`/api/campaigns/${id}/cancel`);
export const exportCampaign = (id) => `/api/campaigns/${id}/export`;

// SSE Progress
export const getCampaignProgressUrl = (id) => `/api/campaigns/${id}/progress`;

// Sample CSV
export const getSampleCsvUrl = () => '/api/campaigns/sample-csv';

// Quick Send (one-off emails)
export const generateQuickEmail = (data) => api.post('/api/quick-send/generate', data);
export const sendQuickEmail = (data) => api.post('/api/quick-send/send', data);

// Tracking
export const getCampaignTracking = (id) => api.get(`/api/campaigns/${id}/tracking`);
export const getQuickSendHistory = () => api.get('/api/quick-send/history');
export const triggerReplyCheck = () => api.post('/api/tracking/check-replies');

// Clay Integration
export const getClaySettings = () => api.get('/api/clay/settings');
export const saveClaySettings = (data) => api.post('/api/clay/settings', data);
export const getClayWebhookUrl = () => api.get('/api/clay/webhook-url');
export const exportToClay = (campaignId) => api.post(`/api/clay/export/${campaignId}`);

// Contacts Directory
export const getContacts = (params) => api.get('/api/contacts', { params });
export const getContact = (id) => api.get(`/api/contacts/${id}`);
export const updateContact = (id, data) => api.put(`/api/contacts/${id}`, data);
export const deleteContact = (id) => api.delete(`/api/contacts/${id}`);
export const getContactStatuses = () => api.get('/api/contacts/statuses');

// Tags
export const getTags = () => api.get('/api/contacts/tags');
export const createTag = (data) => api.post('/api/contacts/tags', data);
export const deleteTag = (id) => api.delete(`/api/contacts/tags/${id}`);
export const addTagToContact = (contactId, data) => api.post(`/api/contacts/${contactId}/tags`, data);
export const removeTagFromContact = (contactId, tagId) => api.delete(`/api/contacts/${contactId}/tags/${tagId}`);

// Reply Hub
export const getReplies = (params) => api.get('/api/replies', { params });
export const getReply = (id) => api.get(`/api/replies/${id}`);
export const classifyReply = (id) => api.post(`/api/replies/${id}/classify`);
export const generateReplyResponse = (id, data) => api.post(`/api/replies/${id}/generate-response`, data);
export const sendReplyResponse = (id, data) => api.post(`/api/replies/${id}/send-response`, data);
export const dismissReply = (id) => api.post(`/api/replies/${id}/dismiss`);
export const getReplyStats = () => api.get('/api/replies/stats');
export const getCalendarStatus = () => api.get('/api/replies/calendar-status');
export const setReplyFollowUp = (replyId, data) => api.post(`/api/replies/${replyId}/set-followup`, data);

// Follow-ups
export const getFollowUps = () => api.get('/api/contacts/follow-ups');
export const generateFollowUp = (contactId) => api.post(`/api/contacts/${contactId}/generate-followup`);

// Workspaces
export const getWorkspaces = () => api.get('/api/workspaces/');
export const createWorkspace = (data) => api.post('/api/workspaces/', data);
export const updateWorkspace = (id, data) => api.put(`/api/workspaces/${id}`, data);
export const deleteWorkspace = (id) => api.delete(`/api/workspaces/${id}`);

// Insights / Feedback Loop
export const getInsights = () => api.get('/api/insights');
export const triggerAnalysis = () => api.post('/api/insights/analyze');
export const getEmailScores = () => api.get('/api/insights/email-scores');

// Attachments
export const uploadAttachments = (files) => {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  return api.post('/api/attachments/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const deleteAttachment = (id) => api.delete(`/api/attachments/${id}`);

// Listing Monitor
export const getMonitoredSites = () => api.get('/api/listings/sites');
export const createMonitoredSite = (data) => api.post('/api/listings/sites', data);
export const updateMonitoredSite = (id, data) => api.put(`/api/listings/sites/${id}`, data);
export const deleteMonitoredSite = (id) => api.delete(`/api/listings/sites/${id}`);
export const checkSiteNow = (id) => api.post(`/api/listings/sites/${id}/check`);
export const checkAllSitesNow = () => api.post('/api/listings/check-all');
export const getListings = (params) => api.get('/api/listings', { params });
export const getListingStats = () => api.get('/api/listings/stats');
export const getListingFilterOptions = () => api.get('/api/listings/filter-options');
export const markListingSeen = (id) => api.post(`/api/listings/${id}/mark-seen`);
export const markAllListingsSeen = (siteId) => api.post(`/api/listings/mark-all-seen${siteId ? `?site_id=${siteId}` : ''}`);
export const updateListingNotes = (id, notes) => api.put(`/api/listings/${id}/notes`, { notes });
export const fetchSiteInfo = (url) => api.post('/api/listings/site-info', { url });
export const getDealCriteria = () => api.get('/api/listings/deal-criteria');
export const updateDealCriteria = (data) => api.put('/api/listings/deal-criteria', data);
export const getStandardCategories = () => api.get('/api/listings/categories/standard');
export const normalizeCategory = (category) => api.post('/api/listings/categories/normalize', { category });
export const quickAddListing = (data) => api.post('/api/listings/quick-add', data);
export const parseEmailPreview = (data) => api.post('/api/listings/parse-email', data);
export const ingestEmailListing = (data) => api.post('/api/listings/ingest-email', data);
export const scanEmailAlerts = (data) => api.post('/api/listings/scan-email-alerts', data);

export default api;
