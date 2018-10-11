function varargout = MHT_plot_TC_calib(MHT)
  % Dennis van Gils
  % 19-03-2018

  % Temperature to calibrate against (deg C)
  applied_degC = MHT.TC_calib.applied_degC;

  % Time shifted to start at 0 s (sec)
  time = MHT.time - MHT.time(1);

  rate_K_per_s = MHT.TC_calib.rate_K_per_s;
  start_degC   = MHT.TC_calib.start_degC;

  % Title
  strTitle = sprintf('%s\nrate = %.1f mK / s', noSubScript(MHT.filename), ...
             rate_K_per_s * 1e3);

  % -------------------------------------------------------------------------
  %  Plot 1
  % -------------------------------------------------------------------------
  cm = darkRainbow(6);

  h1 = figure(1); clf
  set(h1, 'DefaultLineLineWidth', 2)
  set(h1, 'Position', [680 20 1300 1000])

  subplot(2, 1, 1)
  plot(time, MHT.bath_temp_degC, ...
       '-', 'Color', cm(2, :), 'DisplayName', 'bath temp')
  hold on
  plot(time, MHT.LP.bath_temp_degC, ...
       '-r', 'DisplayName', 'bath temp LP')
  plot(time, MHT.tunnel_inlet_degC, ...
       '-c', 'DisplayName', 'PT100')
  plot(time, applied_degC, ...
       '-m', 'DisplayName', 'PT100 LP')
  grid on
  xlabel('time (s)')
  ylabel('temp (°C)')
  legend('Location', 'EO')
  title(strTitle)

  subplot(2, 1, 2)
  offset = 0.002;
  plot(time, ...
       MHT.bath_temp_degC ./ (time * rate_K_per_s + start_degC) - offset, ...
       '-', 'Color', cm(2, :), 'DisplayName', 'bath temp')
  hold on
  plot(time, ...
       MHT.LP.bath_temp_degC ./ (time * rate_K_per_s + start_degC) - offset, ...
       '-r', 'DisplayName', 'bath temp LP')
  plot(time, ...
       MHT.tunnel_inlet_degC ./ (time * rate_K_per_s + start_degC) + offset, ...
       '-c', 'DisplayName', 'PT100')
  plot(time, ...
       applied_degC ./ (time * rate_K_per_s + start_degC) + offset, ...
       '-m', 'DisplayName', 'PT100 LP')
  grid on
  xlabel('time (s)')
  ylabel('temp stability (shifted a.u.)')
  legend('Location', 'EO')

  DvG_layout_plots_style_dark(h1)

  % -------------------------------------------------------------------------
  %  Plot 2
  % -------------------------------------------------------------------------

  h2 = figure(2); clf
  set(h2, 'Position', [680 320 1300 1000])
  set(h2, 'DefaultLineLineWidth', 2)

  subplot(2, 1, 1)
  for iTC = 1:6
    bitV_LP = MHT.LP.(sprintf('TC_%02i_bitV', iTC));

    plot(applied_degC, bitV_LP ./ applied_degC, 'Color', cm(iTC, :), ...
         'DisplayName', sprintf('TC\\_%02i', iTC))
    hold on
  end
  xlabel('PT100 low-passed == ''applied temp'' (°C)')
  ylabel('bitV\_LP / ''applied temp''')
  legend('Location', 'EO')
  title(strTitle)
  xlim([MHT.TC_calib.calib_min_degC MHT.TC_calib.calib_max_degC])

  subplot(2, 1, 2)
  for iTC = 7:12
    bitV_LP = MHT.LP.(sprintf('TC_%02i_bitV', iTC));

    plot(applied_degC, bitV_LP ./ applied_degC, 'Color', cm(iTC - 6, :), ...
         'DisplayName', sprintf('TC\\_%02i', iTC))
    hold on
  end
  xlabel('PT100 low-passed == ''applied temp'' (°C)')
  ylabel('bitV\_LP / ''applied temp''')
  legend('Location', 'EO')
  xlim([MHT.TC_calib.calib_min_degC MHT.TC_calib.calib_max_degC])

  DvG_layout_plots_style_dark(h2)

  if nargout == 2
    varargout{1} = h1;
    varargout{2} = h2;
  end