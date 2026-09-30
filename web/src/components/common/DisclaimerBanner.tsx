import React from 'react';

const DisclaimerBanner: React.FC = () => {
  return (
    <div className="sticky top-16 z-20 bg-yellow-50 border-l-4 border-yellow-400 p-4 my-4 shadow-sm">
      <p className="text-sm text-yellow-800">
        <strong>Disclaimer:</strong> Decision support / educational use only. Not a substitute for formal diagnostic imaging.
      </p>
    </div>
  );
};

export default DisclaimerBanner;
