// FFT worker: generates IQ tone, computes FFT, returns magnitude and frequency arrays
self.addEventListener('message', function(e){
  const d = e.data;
  if(!d || d.cmd!=='preview') return;
  const sample_rate = d.sample_rate || 1e6;
  const tone_freq = d.tone_freq || 1e5;
  const N = d.N || 4096;

  // generate complex signal (real=i, imag=q)
  const re = new Float64Array(N);
  const im = new Float64Array(N);
  for(let n=0;n<N;n++){
    const t = n / sample_rate;
    re[n] = Math.cos(2*Math.PI*tone_freq*t);
    im[n] = Math.sin(2*Math.PI*tone_freq*t);
  }

  // in-place radix-2 Cooley-Tukey FFT
  function fft(re,im){
    const n = re.length;
    const bits = Math.log2(n);
    if(Math.floor(bits)!==bits) throw 'FFT size must be power of two';
    // bit reversal
    for(let i=0;i<n;i++){
      let j=0; for(let b=0;b<bits;b++) j=(j<<1)|((i>>b)&1);
      if(j>i){ let tr=re[i], ti=im[i]; re[i]=re[j]; im[i]=im[j]; re[j]=tr; im[j]=ti; }
    }
    for(let len=2; len<=n; len<<=1){
      const ang = -2*Math.PI/len;
      const wlen_r = Math.cos(ang), wlen_i = Math.sin(ang);
      for(let i=0;i<n;i+=len){
        let wr=1, wi=0;
        for(let j=0;j<len/2;j++){
          const u_r = re[i+j], u_i = im[i+j];
          const v_r = re[i+j+len/2]*wr - im[i+j+len/2]*wi;
          const v_i = re[i+j+len/2]*wi + im[i+j+len/2]*wr;
          re[i+j] = u_r + v_r; im[i+j] = u_i + v_i;
          re[i+j+len/2] = u_r - v_r; im[i+j+len/2] = u_i - v_i;
          const nxt_r = wr*wlen_r - wi*wlen_i;
          const nxt_i = wr*wlen_i + wi*wlen_r;
          wr = nxt_r; wi = nxt_i;
        }
      }
    }
  }

  try{
    fft(re,im);
  }catch(err){
    self.postMessage({error: String(err)});
    return;
  }

  // magnitude and fftshift
  const mag = new Float64Array(N);
  for(let k=0;k<N;k++) mag[k] = Math.sqrt(re[k]*re[k] + im[k]*im[k]);
  // find peak
  let peakIdx = 0;
  let peakVal = -1;
  for(let k=0;k<N;k++){ if(mag[k] > peakVal){ peakVal = mag[k]; peakIdx = k; } }
  const half = N/2;
  const out = new Float64Array(N);
  for(let k=0;k<half;k++){ out[k]=mag[k+half]; out[k+half]=mag[k]; }
  const freqs = new Float64Array(N);
  for(let k=0;k<N;k++) freqs[k] = (k - N/2) * (sample_rate / N);

  // compute peak after fftshift (map index)
  const shiftedPeakIdx = (peakIdx + half) % N;
  const peakFreq = (shiftedPeakIdx - N/2) * (sample_rate / N);
  const peakMag = mag[peakIdx];

  // return ArrayBuffers (transferable) and peak info
  self.postMessage({mag: out.buffer, freqs: freqs.buffer, peakFreq: peakFreq, peakMag: peakMag}, [out.buffer, freqs.buffer]);
});
