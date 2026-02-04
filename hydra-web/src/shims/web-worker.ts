const GlobalWorker = typeof Worker !== 'undefined' ? Worker : null;

const WebWorkerShim =
  GlobalWorker ??
  class {
    constructor() {
      throw new Error('Web Worker is not available in this environment.');
    }
  };

export default WebWorkerShim as unknown as typeof Worker;
