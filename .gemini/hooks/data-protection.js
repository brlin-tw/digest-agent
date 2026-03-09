if (command.includes('rm ') || command.includes('unlink ')) {
  if (command.includes('data/') || command.includes('.db')) {
    throw new Error('🛡️ SRE Guardian: 拒絕刪除 data/ 目錄或數據庫文件！這是敏感資源。');
  }
}