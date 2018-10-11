mht = MHT_readFile('181011_132958.txt', true);

%this_series = mht.T_ambient;
this_series = mht.Q_tunnel;

f_s = 1/mean(diff(mht.time)); % Original sampling frequency [Hz]
f3dB_LP = 0.1;                % Low-pass cut-off frequency: 0.1 [Hz]
[filt_b, filt_a] = butter(2, f3dB_LP / (f_s/2), 'low');

this_series_LP = filtfilt(filt_b, filt_a, this_series);

h1 = figure(2); clf
plot(mht.time, this_series, 'x-')
hold on
plot(mht.time, this_series_LP, '-r')
xlim([200 360])