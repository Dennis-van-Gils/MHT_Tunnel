function MHT = MHT_process_TC_calibration(MHT, ...
                                          calib_min_degC, ...
                                          calib_max_degC ...
                                          )
% Dennis van Gils
% 19-03-2018

% First we need to fix the occasional NaNs in the timeseries.
% Simply replace NaN by the previous non-NaN value.
while sum(isnan(MHT.bath_temp_degC)) > 0
  iNaN = find(isnan(MHT.bath_temp_degC));
  MHT.bath_temp_degC(iNaN) = MHT.bath_temp_degC(iNaN - 1);
end

% The PT100 and thermocouple readings fluctuate so we apply a low-pass
% filter without phase-shift to smoothen the temperature timetraces.

% Create low-pass filter
MHT.LP_settings.f_passband = 0.0025;
MHT.LP_settings.f_stopband = 0.0075;
MHT.LP_settings.passband_ripple = 0.05;
MHT.LP_settings.stopband_attn   = 65;

LP_filt = designfilt('lowpassfir', ...
              'PassbandFrequency'  , MHT.LP_settings.f_passband, ...
              'StopbandFrequency'  , MHT.LP_settings.f_stopband, ...
              'PassbandRipple'     , MHT.LP_settings.passband_ripple, ...
              'StopbandAttenuation', MHT.LP_settings.stopband_attn, ...
              'DesignMethod', 'kaiserwin');

% Low-pass without phase-shift all timeseries 
fns = fieldnames(MHT);
nSamples = length(MHT.time);
for iField = 1:length(fns)
  str_field = fns{iField};
  if strcmp(str_field, 'time') || strcmp(str_field, 'wall_time')
    continue
  elseif length(MHT.(fns{iField})) ~= nSamples
    continue
  end
  MHT.LP.(fns{iField}) = filtfilt(LP_filt, MHT.(fns{iField}));
end

% The temperature recorded by the PT100 sensor (PicoTech PT104) is taken as
% the reference temperature to calibrate against.
% Either fields 'tunnel_inlet_degC' ot 'tunnel_outlet_degC', depending on
% which PT100 probe was inside the temperature bath during calibration.
applied_degC = MHT.LP.tunnel_inlet_degC;

% We cut off possible transient at start and end by limiting the
% temperature span we will calculate the calibration over.

% Determine if the calibration was performed with an increasing or
% decreasing temperature ramp.
if applied_degC(end) > applied_degC(1)
  start_degC = calib_min_degC;
  iStart = find(applied_degC <= calib_min_degC, 1, 'last');
  iEnd = find(applied_degC >= calib_max_degC, 1, 'first');
else
  start_degC = calib_max_degC;
  iStart = find(applied_degC <= calib_max_degC, 1, 'first');
  iEnd = find(applied_degC >= calib_min_degC, 1, 'last');
end

% Adjust all timeseries to the choosen span
fns = fieldnames(MHT);
for iField = 1:length(fns)
  if length(MHT.(fns{iField})) ~= nSamples
    continue
  end
  MHT.(fns{iField}) = MHT.(fns{iField})(iStart:iEnd);
end
fns = fieldnames(MHT.LP);
for iField = 1:length(fns)
  if length(MHT.LP.(fns{iField})) ~= nSamples
    continue
  end
  MHT.LP.(fns{iField}) = MHT.LP.(fns{iField})(iStart:iEnd);
end

applied_degC = applied_degC(iStart:iEnd);

% Temperature change rate [K/s]
rate_K_per_s = (applied_degC(end) - applied_degC(1)) / ...
               (MHT.time(end) - MHT.time(1));

MHT.TC_calib.calib_min_degC = calib_min_degC;
MHT.TC_calib.calib_max_degC = calib_max_degC;
MHT.TC_calib.start_degC     = start_degC;
MHT.TC_calib.rate_K_per_s   = rate_K_per_s;
MHT.TC_calib.applied_degC   = applied_degC;