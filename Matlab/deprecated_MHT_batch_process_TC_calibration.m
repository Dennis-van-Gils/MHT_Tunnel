function MHT_batch_process_TC_calibration()
% Dennis van Gils
% 19-03-2018

% The calibration run spans [14 to 87] deg C. We cut off possible
% transient at start and end by limiting the temperature span we will
% calculate the calibration over.
CALIB_MIN_DEGC = 15;
CALIB_MAX_DEGC = 86;

fileList = dir('TC_calib*.txt');
for iFile = 1:length(fileList)
  fn = fileList(iFile).name;

  MHT = MHT_readFile(fn);
  MHT = MHT_process_TC_calibration(MHT, CALIB_MIN_DEGC, CALIB_MAX_DEGC);
  
  % Save structure to disk
  [~, baseName] = fileparts(MHT.filename);
  save([baseName '.mat'], 'MHT')
  fprintf('Saved to disk: %s\n', [baseName '.mat'])
  
  % Plot
  [h1, h2] = MHT_plot_TC_calib(MHT);
  
  % Save plots
  MHT_saveFig(h1, [baseName '_fig1'])
  MHT_saveFig(h2, [baseName '_fig2'])
end
