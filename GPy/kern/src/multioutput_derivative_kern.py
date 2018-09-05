from .kern import Kern, CombinationKernel
from .multioutput_kern import MultioutputKern, ZeroKern
import numpy as np

class KernWrapper(Kern):
    def __init__(self, fk, fug, fg, base_kern):
        self.fk = fk
        self.fug = fug
        self.fg = fg
        self.base_kern
        super(KernWrapper, self).__init__(1, None, name='KernWrapper',useGPU=False)

    def K(self, X, X2=None):
        return self.fk(X,X2=X2)
    
    def update_gradients_full(self,dL_dK, X, X2=None):
        return self.fug(dK_dK, X, X2=X2)
    
    def gradients_X(self,dL_dK, X, X2=None):
        return self.fg(dL_dK, X, X2=X2)

    def get_gradient(self):
        return self.base_kern.gradient.copy()

    def append_gradient(self, gradient):
        self.base_kern.gradient += gradient

class MultioutputDerivativeKern(MultioutputKern):
    """
    Multioutput derivative kernel is a meta class for combining different kernels for multioutput GPs.
    Multioutput derivative kernel is only a thin wrapper for Multioutput kernel for user not having to define
    cross covariances.
    """
    def __init__(self, kernels, cross_covariances={}, name='MultioutputDerivativeKern'):
        #kernels contains a list of kernels as input, 
        if not isinstance(kernels, list):
            self.single_kern = True
            self.kern = kernels
            kernels = [kernels]
        else:
            self.single_kern = False
            self.kern = kernels
        # The combination kernel ALLWAYS puts the extra dimension last.
        # Thus, the index dimension of this kernel is always the last dimension
        # after slicing. This is why the index_dim is just the last column:
        self.index_dim = -1
        super(MultioutputKern, self).__init__(kernels=kernels, extra_dims=[self.index_dim], name=name, link_parameters=False)

        nl = len(kernels)
         
        #build covariance structure
        covariance = [[None for i in range(nl)] for j in range(nl)]
        linked = []
        for i in range(0,nl):
            unique=True
            for j in range(0,nl):
                if i==j or (kernels[i] is kernels[j]):
                    covariance[i][j] = {'kern': kernels[i],'K':kernels[i].K, 'update_gradients_full': kernels[i].update_gradients_full, 'gradients_X': kernels[i].gradients_X}
                    if i>j:
                        unique=False
                elif cross_covariances.get((i,j)) is not None: #cross covariance is given
                    covariance[i][j] = cross_covariances.get((i,j))
                elif kernels[i].name == 'diffKern' and kernels[i].base_kern == kernels[j]: # one is derivative of other
                    kern = KernWrapper(kernels[i].dK_dX_wrap,kernels[i].update_gradients_dK_dX,kernels[i].gradients_X, kernels[j])
                    covariance[i][j] = {'kern':kern, 'K': kern.K, 'update_gradients_full': kern.update_gradients_full, 'gradients_X': kern.gradients_X}
                    unique=False
                elif kernels[j].name == 'diffKern' and kernels[j].base_kern == kernels[i]: # one is derivative of other
                    kern = KernWrapper(kernels[j].dK_dX2_wrap,kernels[j].update_gradients_dK_dX2,kernels[j].gradients_X2, kernels[i])
                    covariance[i][j] = {'kern':kern, 'K': kern.K, 'update_gradients_full': kern.update_gradients_full, 'gradients_X': kern.gradients_X}
                elif kernels[i].name == 'diffKern' and kernels[j].name == 'diffKern' and kernels[i].base_kern == kernels[j].base_kern: #both are partial derivatives
                    kern = KernWrapper(partial(kernels[i].K, dimX2=kernels[j].dimension), partial(kernels[i].update_gradients_full, dimX2=kernels[j].dimension),None, kernels[i].base_kern)
                    covariance[i][j] = {'kern':kern, 'K': kern.K, 'update_gradients_full': kern.update_gradients_full, 'gradients_X': kern.gradients_X}
                    if i>j:
                        unique=False
                else:
                    kern = ZeroKern()
                    covariance[i][j] = {'kern': kern, 'K': kern.K, 'update_gradients_full': kern.update_gradients_full, 'gradients_X': kern.gradients_X}   
            if unique is True:
                linked.append(i)
        self.covariance = covariance
        self.link_parameters(*[kernels[i] for i in linked])